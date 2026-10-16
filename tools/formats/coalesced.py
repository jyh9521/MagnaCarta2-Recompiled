"""只读解析 Coalesced 字符串对；内存往返，不回写原版数据。"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile

MAX_STRINGS = 100_000
MAX_BYTES = 64 * 1024 * 1024


def write_json_atomic(path, value):
    """以同目录新 inode 替换输出，避免既有输出链接截断只读输入。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as stream:
            temp = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


@dataclass(frozen=True)
class SerializedString:
    text: str
    encoding: str
    offset: int


@dataclass(frozen=True)
class EmbeddedFile:
    path: SerializedString
    content: SerializedString


def _read_string(data, pos):
    begin = pos
    if pos + 4 > len(data):
        raise ValueError("truncated string length")
    units = struct.unpack_from(">i", data, pos)[0]
    pos += 4
    size = units if units >= 0 else -units * 2
    if size > MAX_BYTES or pos + size > len(data):
        raise ValueError("string outside input or size limit")
    raw = data[pos:pos + size]
    pos += size
    if units == 0:
        return SerializedString("", "zero", begin), pos
    if units < 0:
        if not raw.endswith(b"\x00\x00"):
            raise ValueError("missing wide terminator")
        text = raw[:-2].decode("utf-16-le", errors="strict")
        encoding = "utf-16-le"
    else:
        if not raw.endswith(b"\x00"):
            raise ValueError("missing narrow terminator")
        payload = raw[:-1]
        if payload.isascii():
            text, encoding = payload.decode("ascii"), "ascii"
        else:
            try:
                text, encoding = payload.decode("utf-8", errors="strict"), "utf-8"
            except UnicodeError:
                # 保留每个原字节，不宣称 Latin-1 就是游戏实际编码。
                text, encoding = payload.decode("latin1"), "opaque-8bit"
    return SerializedString(text, encoding, begin), pos


def parse(data: bytes) -> list[EmbeddedFile]:
    if len(data) < 4 or len(data) > MAX_BYTES:
        raise ValueError("invalid Coalesced size")
    count = struct.unpack_from(">i", data)[0]
    if count < 0 or count % 2 or count > MAX_STRINGS or count > (len(data) - 4) // 4:
        raise ValueError("invalid string count (expected path/content pairs)")
    pos, files = 4, []
    paths = set()
    for _ in range(count // 2):
        path, pos = _read_string(data, pos)
        content, pos = _read_string(data, pos)
        if not path.text or "\x00" in path.text or path.text.casefold() in paths:
            raise ValueError("empty, embedded-NUL or duplicate path")
        paths.add(path.text.casefold())
        files.append(EmbeddedFile(path, content))
    if pos != len(data):
        raise ValueError("unexpected trailing bytes")
    return files


def _serialize_string(value):
    if value.encoding == "zero":
        if value.text:
            raise ValueError("zero-length string contains text")
        return struct.pack(">i", 0)
    if value.encoding == "utf-16-le":
        raw = value.text.encode("utf-16-le", errors="strict") + b"\x00\x00"
        count = -(len(raw) // 2)
    elif value.encoding in ("ascii", "utf-8", "opaque-8bit"):
        codec = "latin1" if value.encoding == "opaque-8bit" else value.encoding
        raw = value.text.encode(codec, errors="strict") + b"\x00"
        count = len(raw)
    else:
        raise ValueError("unsupported string encoding")
    if len(raw) > MAX_BYTES:
        raise ValueError("string size limit")
    return struct.pack(">i", count) + raw


def serialize(files):
    if len(files) * 2 > MAX_STRINGS:
        raise ValueError("string count limit")
    result = struct.pack(">i", len(files) * 2) + b"".join(
        _serialize_string(s) for f in files for s in (f.path, f.content))
    # 与解析器相同的结构约束；该接口只用于内存往返实验。
    parse(result)
    return result


def script_counts(text):
    return dict(hangul=sum(0xAC00 <= ord(c) <= 0xD7A3 for c in text),
                kana=sum(0x3040 <= ord(c) <= 0x30FF for c in text),
                han=sum(0x4E00 <= ord(c) <= 0x9FFF for c in text))


def extract_entries(files, resource, source_locale="und"):
    """物理行级 INI 值，不声称已解释 UE3 宏/数组/多行语义。"""
    entries = []
    for file in files:
        if file.content.encoding == "opaque-8bit":
            continue
        section, occurrences = "", Counter()
        for line_no, line in enumerate(file.content.text.splitlines(), 1):
            trimmed = line.strip()
            if not trimmed or trimmed.startswith((";", "//", "#")):
                continue
            if re.fullmatch(r"\[[^\]]+\]", trimmed):
                section = trimmed[1:-1]
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            occurrences[(section, key)] += 1
            occurrence = occurrences[(section, key)]
            identity = "\x00".join((resource, file.path.text, section, key, str(occurrence)))
            entries.append(dict(
                id="coalesced:" + hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                resource=resource, embedded_path=file.path.text, section=section,
                key=key, occurrence=occurrence, line=line_no,
                context=f"{file.path.text} [{section}] {key} #{occurrence}",
                source_locale=source_locale, source=value, translation="",
                status="untranslated", reviewer="", syntax_status="physical-line-value"))
    return entries


def analyze(data, resource, source_locale="und"):
    files = parse(data)
    rebuilt = serialize(files)
    if rebuilt != data:
        raise ValueError("byte-identical roundtrip failed")
    entries = extract_entries(files, resource, source_locale)
    documents = [dict(path=f.path.text, path_encoding=f.path.encoding,
                      content_encoding=f.content.encoding, offset=f.content.offset,
                      text=f.content.text, scripts=script_counts(f.content.text)) for f in files]
    return dict(schema_version=1, resource=resource, sha256=hashlib.sha256(data).hexdigest(),
                roundtrip_sha256=hashlib.sha256(rebuilt).hexdigest(), roundtrip_equal=True,
                size=len(data), embedded_file_count=len(files), documents=documents,
                catalog=dict(schema_version=1, entries=entries),
                summary=dict(entry_count=len(entries),
                             opaque_documents=sum(f.content.encoding == "opaque-8bit" for f in files)))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--size", type=int)
    p.add_argument("--sha256", required=True, help="输入成员期望 SHA-256")
    p.add_argument("--resource", required=True, help="稳定的盘内成员路径")
    p.add_argument("--source-locale", default="und", help="显式人工语言标签，不根据后缀猜测")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        p.error("output must differ from input")
    try:
        total = args.input.stat().st_size
        size = total - args.offset if args.size is None else args.size
        if args.offset < 0 or size < 0 or size > MAX_BYTES or args.offset + size > total:
            raise ValueError("invalid input range")
        with args.input.open("rb") as stream:
            stream.seek(args.offset)
            data = stream.read(size)
        if hashlib.sha256(data).hexdigest() != args.sha256.lower():
            raise ValueError("input SHA-256 mismatch")
        report = analyze(data, args.resource, args.source_locale)
        write_json_atomic(args.output, report)
    except (OSError, ValueError, UnicodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(dict(embedded_files=report["embedded_file_count"], **report["summary"], roundtrip_equal=True), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
