"""Read-only verification of a moved workspace and an optional compatibility alias."""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath


def verify(root: Path, manifest: dict, alias: Path | None = None) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir() or not isinstance(manifest, dict) or not manifest:
        raise ValueError('directory and nonempty identity manifest required')
    if alias is not None and not alias.samefile(root):
        raise ValueError('alias does not identify the canonical directory')
    for relative, expected in manifest.items():
        rel = PurePosixPath(relative)
        if not relative or rel.is_absolute() or '..' in rel.parts or '\\' in relative or ':' in relative:
            raise ValueError('invalid relative path: ' + relative)
        if not isinstance(expected, list) or len(expected) != 4 or any(type(x) is not int for x in expected):
            raise ValueError('invalid file identity: ' + relative)
        path = root / relative
        if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
            raise ValueError('file escapes workspace: ' + relative)
        st = path.stat()
        if [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns] != expected:
            raise ValueError('file identity changed: ' + relative)
        if alias is not None and not (alias / relative).samefile(path):
            raise ValueError('alias file mismatch: ' + relative)
    return {'files': len(manifest), 'identity': 'device/inode/size/mtime_ns',
            'alias_verified': alias is not None, 'status': 'PASS',
            'limit': 'Identity preservation, not a fresh content hash or runtime acceptance.'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--alias', type=Path)
    a = p.parse_args(argv)
    print(json.dumps(verify(a.root, json.loads(a.manifest.read_text(encoding='utf-8')), a.alias), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
