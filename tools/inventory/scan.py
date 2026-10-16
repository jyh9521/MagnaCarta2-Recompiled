"""只读资源清单：目录、显式文件和 XDVDFS 光盘；不解密、不回写。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

VERSION = "0.1.0"
SECTOR = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"
BASES = (0, 0xFB20, 0x20600, 0x2080000, 0xFD90000)


def read_at(stream, offset, size, total):
    if offset < 0 or size < 0 or offset + size > total:
        raise ValueError("range outside input")
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("short read")
    return data


def identify(head):
    if head.startswith(b"XEX2"):
        return "xex2", "header-only"
    if head[:4] in (b"\x9e\x2a\x83\xc1", b"\xc1\x83\x2a\x9e"):
        return "unreal-package-candidate", "magic-only"
    if head.startswith(b"BIK"):
        return "bink-candidate", "magic-only"
    if head.startswith(b"RIFF"):
        return "riff-candidate", "magic-only"
    return "unknown", "not-parsed"


def digest_range(stream, offset, size, total):
    if offset < 0 or offset + size > total:
        raise ValueError("range outside input")
    stream.seek(offset)
    h = hashlib.sha256()
    remaining = size
    while remaining:
        block = stream.read(min(1024 * 1024, remaining))
        if not block:
            raise ValueError("short read while hashing")
        h.update(block)
        remaining -= len(block)
    return h.hexdigest()


def xdvdfs_entries(stream, total):
    """返回分区偏移和目录成员；校验范围、环、名称和重复路径。"""
    base = next((b for b in BASES if b + 0x10800 <= total and
                 read_at(stream, b + 0x10000, 20, total) == MAGIC), None)
    if base is None:
        raise ValueError("XDVDFS descriptor not found at supported offsets")
    descriptor = read_at(stream, base + 0x10000, SECTOR, total)
    if descriptor[-20:] != MAGIC:
        raise ValueError("XDVDFS trailing magic mismatch")
    sector, length = struct.unpack_from("<II", descriptor, 20)
    pending = [(sector, length, "", 0)]
    tables, names, entries = set(), set(), []
    while pending:
        sector, length, parent, depth = pending.pop()
        if depth > 128 or not 14 <= length <= 32 * 1024 * 1024:
            raise ValueError("invalid directory depth or length")
        table_key = (sector, length)
        if table_key in tables:
            raise ValueError("directory cycle or repeated directory table")
        tables.add(table_key)
        table = read_at(stream, base + sector * SECTOR, length, total)
        nodes, visited = [0], set()
        while nodes:
            position = nodes.pop()
            if position in visited or position + 14 > length:
                raise ValueError("invalid directory node or cycle")
            visited.add(position)
            left, right, start, size, attributes, count = struct.unpack_from("<HHIIBB", table, position)
            if not count or position + 14 + count > length:
                raise ValueError("invalid filename length")
            raw = table[position + 14:position + 14 + count]
            name = raw.decode("ascii", errors="surrogateescape")
            if name in (".", "..") or any(c in name for c in "/\\\x00"):
                raise ValueError("invalid member name")
            path = parent + name
            if path.casefold() in names:
                raise ValueError("duplicate member path")
            names.add(path.casefold())
            offset = base + start * SECTOR
            if offset + size > total:
                raise ValueError("member outside input")
            if attributes & 0x10:
                if size:
                    pending.append((start, size, path + "/", depth + 1))
            else:
                entries.append((path, offset, size))
            for child in (right, left):
                if child:
                    nodes.append(child * 4)
    return base, sorted(entries)


def record(stream, path, offset, size, total, disc):
    head = read_at(stream, offset, min(size, 32), total)
    kind, status = identify(head)
    result = dict(path=path, size=size, extension=Path(path.split("::", 1)[-1]).suffix.lower(),
                  type=kind, parse_status=status, disc=disc, offset=offset,
                  sha256=digest_range(stream, offset, size, total),
                  related_resources=[], relationship_status="not-analyzed")
    if kind == "xex2" and size >= 24:
        flags, pe_offset, reserved, security_offset, count = struct.unpack_from(">5I", head, 4)
        result["xex_header"] = dict(module_flags=flags, pe_data_offset=pe_offset,
                                   security_info_offset=security_offset, optional_header_count=count)
        result["parse_status"] = "fixed-header-only"
    if kind == "unreal-package-candidate" and size >= 8:
        order = ">" if head[:4] == b"\x9e\x2a\x83\xc1" else "<"
        word = struct.unpack_from(order + "I", head, 4)[0]
        result["package_version_candidate"] = dict(
            raw_word=word, version=word & 0xFFFF, licensee_version=word >> 16,
            byte_order="big" if order == ">" else "little")
    return result


def scan(inputs, disc="unspecified", images=False, exclude=None):
    result = dict(schema_version=1, tool_version=VERSION, files=[], errors=[], summary={})
    candidates = []
    for value in inputs:
        p = Path(value)
        if p.is_symlink() or p.is_junction():
            result["errors"].append(dict(path=p.name, error="linked input skipped"))
        elif p.is_dir():
            def onerror(error):
                result["errors"].append(dict(path=str(Path(error.filename).name), error=str(error)))
            for folder, dirs, files in os.walk(p, followlinks=False, onerror=onerror):
                for name in list(dirs):
                    linked = Path(folder) / name
                    if linked.is_symlink() or linked.is_junction():
                        dirs.remove(name)
                        result["errors"].append(dict(path=linked.relative_to(p).as_posix(), error="linked directory skipped"))
                candidates.extend((Path(folder) / name, (Path(folder) / name).relative_to(p).as_posix()) for name in files)
        else:
            candidates.append((p, p.name))
    seen = set()
    for p, label in sorted(candidates, key=lambda x: (x[1], str(x[0]))):
        if exclude is not None and p.resolve() == Path(exclude).resolve():
            continue
        try:
            if p.is_symlink() or p.is_junction():
                raise ValueError("linked input skipped")
            if label.casefold() in seen:
                raise ValueError("duplicate input label; scan roots separately")
            seen.add(label.casefold())
            before = p.stat()
            with p.open("rb") as stream:
                item = record(stream, label, 0, before.st_size, before.st_size, disc)
                if images:
                    base, members = xdvdfs_entries(stream, before.st_size)
                    item.update(type="xdvdfs", parse_status="directory-parsed", partition_offset=base)
                    result["files"].append(item)
                    for name, offset, size in members:
                        result["files"].append(record(stream, label + "::" + name, offset, size, before.st_size, disc))
                else:
                    result["files"].append(item)
            after = p.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError("input changed during scan; discard this manifest")
        except (OSError, ValueError, struct.error) as error:
            result["errors"].append(dict(path=label, error=str(error)))
    result["summary"] = dict(record_count=len(result["files"]),
                             total_record_bytes=sum(f["size"] for f in result["files"]),
                             error_count=len(result["errors"]))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--disc", default="unspecified")
    parser.add_argument("--xdvdfs", action="store_true", help="所有输入按 XDVDFS 镜像解析")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    for source in args.inputs:
        resolved = source.resolve()
        if output == resolved or (resolved.is_dir() and output.is_relative_to(resolved)):
            parser.error("output must be outside all input roots")
    data = scan(args.inputs, args.disc, args.xdvdfs)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         delete=False, suffix=".tmp") as temporary:
            temp = Path(temporary.name)
            json.dump(data, temporary, ensure_ascii=True, indent=2)
            temporary.write("\n")
        os.replace(temp, output)
    except OSError as error:
        if "temp" in locals():
            temp.unlink(missing_ok=True)
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(data["summary"], sort_keys=True))
    return 1 if data["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
