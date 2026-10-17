"""Check tracked Markdown prose without rewriting code, identifiers or URLs."""
import argparse
from pathlib import Path
import re
import subprocess

PERSONAL = re.compile(r'用户|使用者|我们|咱们|本人|你们|您|你|我|他们|她们|\b(?:users?|you|your|yours|we|our|ours|us|they|their|theirs)\b', re.I)


def prose_lines(text):
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            token = match[1]
            if fence is None: fence = token
            elif token[0] == fence[0] and len(token) >= len(fence): fence = None
            continue
        if fence is not None or line.startswith(('    ', '\t')): continue
        line = re.sub(r'(`+).*?\1', '', line)
        line = re.sub(r'https?://[^\s)>]+', '', line)
        yield number, line


def audit(text):
    return [dict(line=number, term=match[0]) for number, line in prose_lines(text)
            for match in PERSONAL.finditer(line)]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--root', type=Path, default=Path.cwd())
    args = p.parse_args(argv); root = args.root.resolve(strict=True)
    top = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=root, text=True).strip()
    if Path(top).resolve() != root: raise ValueError('Markdown validation requires the repository root')
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    errors = []; count = 0
    for name in (n for n in names if n and Path(n).suffix.lower() == '.md'):
        count += 1
        errors.extend(dict(file=name, **row) for row in audit((root/name).read_text(encoding='utf-8-sig')))
    for row in errors: print(f"MARKDOWN_STYLE file={row['file']} line={row['line']} personal_reference=1")
    if not count: raise ValueError('no tracked Markdown files')
    print(f'MARKDOWN_STYLE files={count} issues={len(errors)}')
    return int(bool(errors))


if __name__ == '__main__': raise SystemExit(main())
