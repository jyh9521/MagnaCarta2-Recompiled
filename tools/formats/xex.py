"""Bounded, read-only XEX2 metadata reader. Never emits key/signature payloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile


class XexError(ValueError):
    """Invalid or unsupported metadata structure."""


NAMES = {0x2FF: "resource_info", 0x3FF: "file_format_info",
         0x10100: "entry_point", 0x10201: "image_base_address",
         0x103FF: "import_libraries", 0x18002: "checksum_timestamp",
         0x183FF: "original_pe_name", 0x200FF: "static_libraries",
         0x20104: "tls_info", 0x20200: "default_stack_size",
         0x30000: "system_flags", 0x40006: "execution_info",
         0x40201: "title_workspace_size", 0x40310: "game_ratings",
         0x40404: "lan_key", 0x405FF: "xbox360_logo",
         0x406FF: "multidisc_media_ids"}


def version(value: int) -> str:
    return f"{value >> 28}.{(value >> 24) & 15}.{(value >> 8) & 65535}.{value & 255}"


def parse_xex(data: bytes) -> dict:
    """Parse structural metadata, not cryptographic authenticity or PPC code."""
    def bounds(off, size, limit=None):
        limit = len(data) if limit is None else limit
        if off < 0 or size < 0 or off > limit or size > limit - off:
            raise XexError(f"range out of bounds: offset={off} size={size} limit={limit}")

    def u32(off):
        bounds(off, 4)
        return struct.unpack_from(">I", data, off)[0]

    bounds(0, 24)
    if data[:4] != b"XEX2":
        raise XexError("expected XEX2 magic")
    flags, pe, reserved, security, count = struct.unpack_from(">5I", data, 4)
    bounds(0, pe)
    bounds(24, count * 8, pe)
    table_end = 24 + count * 8
    result = {"schema_version": 1, "sha256": hashlib.sha256(data).hexdigest(),
              "file_size": len(data), "module_flags": flags,
              "pe_data_offset": pe, "reserved": reserved,
              "security_info_offset": security, "optional_header_count": count,
              "validation": "metadata-structure-only; signatures/digests not authenticated",
              "optional_headers": []}
    regions = [(0, table_end, "fixed-header-table")]
    bounds(security, 0x184, pe)
    sec_size, image_size = u32(security), u32(security + 4)
    if sec_size < 0x184:
        raise XexError("short security structure")
    bounds(security, sec_size, pe)
    page_count = u32(security + 0x180)
    bounds(security + 0x184, page_count * 24, security + sec_size)
    result["security"] = {"header_size": sec_size, "image_size": image_size,
        **{name: u32(security + off) for name, off in [
            ("image_flags", 0x10c), ("load_address", 0x110),
            ("import_table_count", 0x128), ("export_table", 0x160),
            ("region", 0x178), ("allowed_media_types", 0x17c)]},
        "page_descriptor_count": page_count,
        "page_descriptors": [{"type": u32(security + 0x184 + i * 24) & 15,
            "page_count": u32(security + 0x184 + i * 24) >> 4}
            for i in range(page_count)],
        "sensitive_fields": "omitted (signature, key material and digests)"}
    regions.append((security, security + sec_size, "security"))
    seen = set()
    for i in range(count):
        key, value = struct.unpack_from(">II", data, 24 + i * 8)
        if key in seen:
            raise XexError(f"duplicate optional header {key:08x}")
        seen.add(key)
        kind = key & 255
        item = {"key": f"0x{key:08X}", "name": NAMES.get(key, "unknown"),
                "table_offset": 24 + i * 8}
        result["optional_headers"].append(item)
        if kind in (0, 1):
            item.update(storage="inline", value=value)
            continue
        bounds(value, 4, pe)
        size = u32(value) if kind == 255 else kind * 4
        if size < 4:
            raise XexError("short optional header")
        bounds(value, size, pe)
        regions.append((value, value + size, item["name"]))
        item.update(storage="offset", offset=value, size=size,
                    decode_status="structure-only")
        end = value + size
        if key == 0x40006:
            if size != 24:
                raise XexError("invalid execution info size")
            media, ver, base, title, platform, exe_table, disc, discs, save = struct.unpack_from(
                ">4I4BI", data, value)
            item["decoded"] = {"media_id": f"0x{media:08X}", "title_id": f"0x{title:08X}",
                "version_raw": ver, "version": version(ver), "base_version_raw": base,
                "base_version": version(base), "platform": platform,
                "executable_table": exe_table, "disc_number": disc, "disc_count": discs,
                "savegame_id": f"0x{save:08X}"}
            result["execution_info"] = item["decoded"]
        elif key == 0x3FF:
            bounds(value, 8, end)
            enc, comp = struct.unpack_from(">HH", data, value + 4)
            decoded = {"encryption_type": enc, "compression_type": comp}
            if comp == 1:
                if (size - 8) % 8:
                    raise XexError("invalid basic compression block table")
                decoded["basic_blocks"] = [{"data_size": u32(p), "zero_size": u32(p + 4)}
                    for p in range(value + 8, end, 8)]
                decoded["decompressed_size"] = sum(x["data_size"] + x["zero_size"] for x in decoded["basic_blocks"])
                decoded["stored_data_size"] = sum(x["data_size"] for x in decoded["basic_blocks"])
            elif comp == 2:
                bounds(value, 36, end)
                decoded.update(window_size=u32(value + 8), first_block_size=u32(value + 12))
            item["decoded"] = decoded
            result["file_format"] = decoded
        elif key == 0x103FF:
            bounds(value, 12, end)
            string_size, name_count = u32(value + 4), u32(value + 8)
            bounds(value + 12, string_size, end)
            names, pos, stop = [], value + 12, value + 12 + string_size
            if name_count > string_size:
                raise XexError("invalid import name count")
            for _ in range(name_count):
                zero = data.find(b"\0", pos, stop)
                if zero < 0:
                    raise XexError("unterminated import library name")
                names.append(data[pos:zero].decode("ascii", "strict"))
                pos = value + 12 + ((zero + 1 - value - 12 + 3) & ~3)
            libraries, pos = [], stop
            while pos < end:
                bounds(pos, 40, end)
                lib_size = u32(pos)
                name_index, imports = struct.unpack_from(">HH", data, pos + 36)
                index = name_index & 255
                if lib_size < 40 or lib_size != 40 + imports * 4 or index >= len(names):
                    raise XexError("invalid import library size/count/name index")
                bounds(pos, lib_size, end)
                libraries.append({"name": names[index], "offset": pos,
                    "size": lib_size, "id": u32(pos + 24), "version": version(u32(pos + 28)),
                    "minimum_version": version(u32(pos + 32)), "name_index_raw": name_index,
                    "import_count": imports,
                    "import_record_addresses": [u32(p) for p in range(pos + 40, pos + lib_size, 4)],
                    "ordinal_resolution": "requires loaded/decrypted image; addresses are not ordinals"})
                pos += lib_size
            item["decoded"] = {"names": names, "libraries": libraries}
            result["import_libraries"] = libraries
        elif key == 0x200FF:
            if (size - 4) % 16:
                raise XexError("invalid static library table size")
            item["decoded"] = [{"name": data[p:p+8].rstrip(b"\0").decode("ascii"),
                "version": ".".join(map(str, (*struct.unpack_from(">3H", data, p + 8), data[p + 15]))),
                "approval_type": data[p + 14]} for p in range(value + 4, end, 16)]
        elif key == 0x183FF:
            item["decoded"] = {"name": data[value+4:end].split(b"\0", 1)[0].decode("ascii")}
        elif key == 0x20104:
            item["decoded"] = dict(zip(("slot_count", "raw_data_address", "data_size", "raw_data_size"),
                                        struct.unpack_from(">4I", data, value)))
        elif key == 0x18002:
            item["decoded"] = {"checksum": u32(value), "timestamp": u32(value + 4)}
        elif key == 0x2FF:
            if (size - 4) % 16:
                raise XexError("invalid resource table size")
            item["decoded"] = [{"name": data[p:p+8].rstrip(b"\0").decode("ascii"),
                "address": u32(p+8), "size": u32(p+12)} for p in range(value+4, end, 16)]
        elif key == 0x40404:
            item["decode_status"] = "sensitive-payload-omitted"
        elif key == 0x40310:
            item["decoded"] = {"rating_codes": list(data[value:end]),
                               "meaning": "raw jurisdiction slots; no rating-name inference"}
        elif key == 0x405FF:
            item["decoded"] = {"encoded_logo_size": size - 4,
                               "image_decode_status": "not-decoded"}
        elif key == 0x406FF:
            if (size - 4) % 16:
                raise XexError("invalid multidisc media ID table size")
            item["decoded"] = {"count": (size - 4) // 16,
                "media_ids": [data[p:p+16].hex() for p in range(value+4, end, 16)]}
        if "decoded" in item:
            item["decode_status"] = "decoded"
    regions.sort()
    for left, right in zip(regions, regions[1:]):
        if left[1] > right[0]:
            raise XexError(f"overlapping header regions: {left[2]} / {right[2]}")
    result["header_ranges"] = [{"offset": a, "size": b-a, "name": name} for a,b,name in regions]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--offset", type=lambda s: int(s, 0), default=0)
    parser.add_argument("--size", type=lambda s: int(s, 0))
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if (args.input.resolve() == args.output.resolve() or
                (args.output.exists() and os.path.samefile(args.input, args.output))):
            raise XexError("output must differ from input")
        total = args.input.stat().st_size
        size = args.size if args.size is not None else total - args.offset
        if args.offset < 0 or size < 24 or size > 256 * 1024 * 1024 or args.offset + size > total:
            raise XexError("invalid input slice (maximum 256 MiB)")
        with args.input.open("rb") as handle:
            handle.seek(args.offset)
            data = handle.read(size)
        if args.expected_sha256 and hashlib.sha256(data).hexdigest() != args.expected_sha256.lower():
            raise XexError("input SHA-256 mismatch")
        result = parse_xex(data)
        result["source"] = {"name": args.input.name, "offset": args.offset, "size": size}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent,
                    prefix=args.output.name + ".", suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
            os.replace(temporary, args.output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(f"XEX_METADATA_OK optional_headers={result['optional_header_count']} libraries={len(result.get('import_libraries', []))}")
        return 0
    except (OSError, ValueError, struct.error) as exc:
        print(f"XEX_ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
