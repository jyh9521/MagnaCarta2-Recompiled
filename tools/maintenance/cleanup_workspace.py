"""Hash-verified duplicate retirement with explicit retention and reversible copies.

Only duplicate binary outputs below local/analysis are retired. Source, evidence
text, original disc images, upstream dependencies and compatibility links remain.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat

SUFFIXES = {'.exe', '.dll', '.obj', '.xex', '.bin', '.ppm', '.png', '.bik', '.xxx'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('expected relative POSIX path')
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in ('', '.', '..') for x in value.split('/')):
        raise ValueError('invalid relative path')
    if any(x == '.git' or x.endswith((' ', '.')) for x in p.parts):
        raise ValueError('excluded path component')
    return p


def checked(root, name, *, exists=True):
    p = root.joinpath(*relative(name).parts)
    for part in (p, *p.parents):
        if part == root:
            break
        if part.is_symlink() or part.is_junction():
            raise ValueError('linked path excluded')
    if not p.resolve().is_relative_to(root) or p == root:
        raise ValueError('path escapes workspace')
    if exists and not p.exists():
        raise ValueError('required path missing: ' + name)
    return p


def regular(path):
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or path.is_symlink():
        raise ValueError('expected regular non-linked file')
    return s


def identity(info):
    # Hashing may itself update access time; content/membership guards exclude it.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and (path.is_symlink() or path.stat().st_nlink != 1):
        raise ValueError('linked record excluded')
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def eligible(name):
    p = relative(name)
    return p.parts[:2] == ('local', 'analysis') and p.suffix.lower() in SUFFIXES


def protected(name, keep):
    return any(name == value or name.startswith(value + '/') for value in keep)


def registry(root):
    path = checked(root, 'local/maintenance/retired-keepers.json', exists=False)
    if not path.exists(): return dict(schema=1, keepers={}, reports=[])
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('schema') != 1 or not isinstance(value.get('keepers'), dict):
        raise ValueError('invalid keeper registry')
    for name, identity_row in value['keepers'].items():
        if not eligible(name): raise ValueError('invalid registered keeper')
        verify_file(checked(root, name), identity_row)
    return value


def make_plan(root, keep, minimum=65536):
    root = Path(root).resolve(strict=True)
    if not root.is_dir() or not keep or type(minimum) is not int or minimum < 1:
        raise ValueError('workspace, explicit retention and positive minimum required')
    # Retained copies from earlier retirements are durable restoration anchors.
    keep = sorted(set(str(relative(x)) for x in keep) | set(registry(root)['keepers']))
    for name in keep:
        checked(root, name)
    scope = checked(root, 'local/analysis')
    by_size = {}
    for base, dirs, files in os.walk(scope, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != '.git' and
                         not Path(base, d).is_symlink() and not Path(base, d).is_junction())
        for name in sorted(files):
            p = Path(base, name); rel = p.relative_to(root).as_posix()
            if not eligible(rel): continue
            try:
                s = regular(p)
            except (ValueError, OSError): continue
            if s.st_size >= minimum: by_size.setdefault(s.st_size, []).append(rel)
    groups, skipped_unique = [], 0
    for size, names in sorted(by_size.items()):
        if len(names) < 2: continue
        hashes = {}
        for name in names:
            p = checked(root, name); before = regular(p); h = digest(p)
            if identity(regular(p)) != identity(before):
                raise ValueError('input changed while hashing: ' + name)
            hashes.setdefault(h, []).append(name)
        for h, members in sorted(hashes.items()):
            members.sort()
            retained = [n for n in members if protected(n, keep)]
            keeper = retained[0] if retained else members[0]
            retired = [n for n in members if n != keeper and not protected(n, keep)]
            if not retired:
                skipped_unique += 1; continue
            groups.append(dict(sha256=h, size=size, keeper=keeper,
                               retired=[dict(path=n, mtime_ns=regular(root/n).st_mtime_ns)
                                        for n in retired]))
    return dict(schema=1, root=str(root), keep=keep, groups=groups,
                retired_files=sum(len(g['retired']) for g in groups),
                reclaim_bytes=sum(g['size']*len(g['retired']) for g in groups),
                scope='exact duplicate binary outputs only; all unique files retained')


def validate(plan):
    if not isinstance(plan, dict) or plan.get('schema') != 1 or not plan.get('keep'):
        raise ValueError('invalid plan/retention')
    root = Path(plan['root']).resolve(strict=True)
    if str(root) != plan['root']: raise ValueError('plan root must be canonical')
    keep = [str(relative(x)) for x in plan['keep']]
    for name in keep: checked(root, name)
    seen = set()
    for group in plan['groups']:
        if not re.fullmatch('[0-9a-f]{64}', str(group['sha256'])) or type(group['size']) is not int or group['size'] < 1:
            raise ValueError('invalid group identity')
        if not eligible(group['keeper']) or not group['retired']:
            raise ValueError('invalid keeper/group')
        for name in [group['keeper'], *(x['path'] for x in group['retired'])]:
            if not eligible(name) or name in seen: raise ValueError('duplicate/out-of-scope member')
            seen.add(name); checked(root, name, exists=name == group['keeper'])
        for row in group['retired']:
            if protected(row['path'], keep) or type(row.get('mtime_ns')) is not int or row['mtime_ns'] < 0:
                raise ValueError('protected member or invalid timestamp')
    if plan.get('retired_files') != sum(len(g['retired']) for g in plan['groups']) or plan.get('reclaim_bytes') != sum(g['size']*len(g['retired']) for g in plan['groups']):
        raise ValueError('plan totals mismatch')
    return root


def verify_file(path, group):
    if regular(path).st_size != group['size'] or digest(path) != group['sha256']:
        raise ValueError('file identity mismatch: ' + str(path))


def apply(plan, report_path):
    root = validate(plan)
    report_path = Path(report_path).absolute()
    # The plan and report remain separate from all file targets and keepers.
    selected = {str(root/name) for g in plan['groups'] for name in
                [g['keeper'], *(x['path'] for x in g['retired'])]}
    if str(report_path) in selected or report_path.exists():
        raise ValueError('report must be new and outside selected files')
    # Complete preflight precedes any retirement.
    for group in plan['groups']:
        verify_file(checked(root, group['keeper']), group)
        for row in group['retired']: verify_file(checked(root, row['path']), group)
    report = dict(schema=1, status='in-progress', plan=plan, removed=[], freed_bytes=0)
    save(report_path, report)
    retained = registry(root)
    for group in plan['groups']:
        retained['keepers'][group['keeper']] = dict(sha256=group['sha256'], size=group['size'])
    retained['reports'].append(str(report_path))
    save(checked(root, 'local/maintenance/retired-keepers.json', exists=False), retained)
    try:
        for group in plan['groups']:
            for row in group['retired']:
                keeper = checked(root, group['keeper']); target = checked(root, row['path'])
                verify_file(keeper, group); verify_file(target, group)
                # Journal intent first: interruption after unlink remains restorable.
                report['removed'].append(row['path']); save(report_path, report)
                target.unlink()
                report['freed_bytes'] += group['size']
                save(report_path, report)
        report['status'] = 'completed'; save(report_path, report)
    except Exception as exc:
        report['status'] = 'failed'; report['error'] = str(exc); save(report_path, report); raise
    return report


def restore(report, prefixes=None):
    if report.get('schema') != 1 or report.get('status') not in ('completed', 'failed', 'in-progress'):
        raise ValueError('invalid cleanup report')
    plan = report['plan']; root = validate(plan)
    known = {x['path'] for g in plan['groups'] for x in g['retired']}
    removed = report['removed']
    if len(set(removed)) != len(removed) or not set(removed) <= known:
        raise ValueError('invalid removed set')
    if prefixes is not None:
        if not prefixes: raise ValueError('empty restoration selection')
        prefixes = [str(relative(x)) for x in prefixes]
        removed = [n for n in removed if protected(n, prefixes)]
        if not removed: raise ValueError('restoration selection matches no retired paths')
    # Restore journaled targets; never overwrite an existing changed file.
    for group in plan['groups']:
        if not any(x['path'] in removed for x in group['retired']): continue
        verify_file(checked(root, group['keeper']), group)
        for row in group['retired']:
            if row['path'] in removed:
                p = checked(root, row['path'], exists=False)
                if p.exists(): verify_file(p, group)
    count = 0
    for group in plan['groups']:
        for row in group['retired']:
            if row['path'] not in removed: continue
            dst = checked(root, row['path'], exists=False)
            if dst.exists(): continue
            src = checked(root, group['keeper']); verify_file(src, group)
            dst.parent.mkdir(parents=True, exist_ok=True)
            temp = dst.with_name(dst.name + '.restore-pending')
            with src.open('rb') as inp, temp.open('xb') as out: shutil.copyfileobj(inp, out, 1024*1024)
            verify_file(temp, group)
            temp.rename(dst); os.utime(dst, ns=(row['mtime_ns'], row['mtime_ns']))
            verify_file(dst, group); count += 1
    return dict(status='restored', restored_files=count)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('plan'); p.add_argument('--root', type=Path, required=True)
    p.add_argument('--policy', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('apply'); p.add_argument('--plan', type=Path, required=True); p.add_argument('--report', type=Path, required=True)
    p = sub.add_parser('restore'); p.add_argument('--report', type=Path, required=True)
    p.add_argument('--prefix', action='append', help='restore only matching relative file/directory paths')
    args = parser.parse_args(argv)
    if args.mode == 'plan':
        if args.output.exists(): raise ValueError('plan output must be new')
        policy = json.loads(args.policy.read_text(encoding='utf-8-sig'))
        result = make_plan(args.root, policy['keep']); save(args.output, result)
        print(f"CLEANUP_PLAN files={result['retired_files']} reclaim_bytes={result['reclaim_bytes']}")
    elif args.mode == 'apply':
        result = apply(json.loads(args.plan.read_text(encoding='utf-8-sig')), args.report)
        print(f"CLEANUP_APPLY files={len(result['removed'])} freed_bytes={result['freed_bytes']} status={result['status']}")
    else:
        result = restore(json.loads(args.report.read_text(encoding='utf-8-sig')), args.prefix)
        print(f"CLEANUP_RESTORE files={result['restored_files']} status=restored")
    return 0


if __name__ == '__main__': raise SystemExit(main())
