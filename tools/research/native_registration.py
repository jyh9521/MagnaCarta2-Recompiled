"""Read-only native name lookup recovery for the hash-locked MC2 executable.

The generated PPC address set is an entry-boundary witness, never an ABI proof.
Only nonzero, null-terminated stride-eight tables are implementation mappings;
zero static slots and package/class ambiguity remain explicitly unresolved.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.research.verify_branch_ranges import BASE, image_from_xex
from tools.formats.coalesced import write_json_atomic

NAME_RE = re.compile(r"int([AU])([A-Za-z_][A-Za-z0-9_]*)exec([A-Za-z_][A-Za-z0-9_]*)\Z")
CORE_TABLE = 0x8320EC20
CORE_LOOKUP = 0x823C7F40
GNATIVES = 0x83250D80
REGISTER_SHA256 = "64e962b32141dacc7236876a62101d391599e21cabde78fb538ecc4815979669"
UFUNCTION_SHA256 = "e85657c5262ecae241960f91bbe2d883bf0d58bac4a858d76581d02346087714"
# Three first literals follow non-string data without preceding NUL. These
# version-locked exceptions are not a generic suffix-scanning permission.
PACKED_NAME_STARTS = (0x820C2030, 0x821517C0, 0x82156C20)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def native_names(image, base=BASE, allowed_starts=()):
    """Full, aligned, NUL-terminated UTF-16BE names, not suffix matches."""
    result = {}
    for match in re.finditer(b"\x00i\x00n\x00t\x00[AU]", image):
        start = match.start()
        if start % 2 or (start and image[start-2:start] != b"\0\0" and base+start not in allowed_starts):
            continue
        end = start
        while end + 2 <= len(image) and image[end:end+2] != b"\0\0" and end-start <= 512:
            end += 2
        if end + 2 > len(image) or end-start > 512:
            continue
        try:
            text = image[start:end].decode("utf-16-be", errors="strict")
        except UnicodeDecodeError:
            continue
        parsed = NAME_RE.fullmatch(text)
        if parsed:
            result[base+start] = {"registration_name": text, "class_prefix": parsed[1],
                                  "class": parsed[2], "function": parsed[3]}
    return result


def recover_tables(image, entries, base=BASE, allowed_starts=()):
    """Require valid name pointer + independently generated function boundary.

    A table is a same-class run of eight-byte records followed by {0,0}.
    Lone string pointers, arbitrary in-range code pointers, and zero slots do
    not become executable mappings. Pointers are big-endian and four-aligned.
    """
    names = native_names(image, base, allowed_starts)
    pairs = {}
    zero_slots = []
    for offset in range(0, len(image)-7, 4):
        name, target = struct.unpack_from(">II", image, offset)
        if name not in names:
            continue
        record = dict(names[name], record_address=base+offset, name_address=name,
                      implementation=target)
        if target in entries:
            pairs[base+offset] = record
        elif target == 0:
            zero_slots.append(record)
    tables, accepted = [], set()
    for address in sorted(pairs):
        if address in accepted:
            continue
        first = pairs[address]
        # A preceding same-class record means this is not a table start.
        previous = pairs.get(address-8)
        if previous and previous["class"] == first["class"] and previous["class_prefix"] == first["class_prefix"]:
            continue
        records, cursor = [], address
        while cursor in pairs and pairs[cursor]["class"] == first["class"] and pairs[cursor]["class_prefix"] == first["class_prefix"]:
            records.append(pairs[cursor]); cursor += 8
        offset = cursor-base
        if offset < 0 or offset+8 > len(image) or image[offset:offset+8] != bytes(8):
            continue
        accepted.update(record["record_address"] for record in records)
        tables.append({"address": address, "terminator": cursor, "stride": 8,
                       "class": first["class"], "class_prefix": first["class_prefix"],
                       "records": records,
                       "table_sha256": digest(image[address-base:cursor-base+8])})
    return {"tables": tables, "static_zero_slots": zero_slots,
            "unaccepted_nonzero_pairs": [pairs[a] for a in sorted(set(pairs)-accepted)],
            "named_strings": len(names)}


def map_declarations(report, tables, zero_slots):
    """Join class + exact source identifier, retaining all binding candidates."""
    records = defaultdict(list)
    zeros = defaultdict(list)
    for table in tables:
        for record in table["records"]:
            records[(record["class"], record["function"])].append(record)
    for record in zero_slots:
        zeros[(record["class"], record["function"])].append(record)
    output = []
    seen = set()
    declaration_names = Counter(f["path"] for f in report["functions"] if f.get("is_native"))
    for function in report["functions"]:
        if not function.get("is_native"):
            continue
        identity = function["package"], function["export"]
        if identity in seen:
            raise ValueError("duplicate UFunction identity")
        seen.add(identity)
        if function.get("metadata_status") != "validated" or not function["function_flags"] & 0x400:
            raise ValueError("native declaration metadata is not validated")
        parts = function["path"].split(".")
        candidates = records.get(tuple(parts), []) if len(parts) == 2 else []
        null_candidates = zeros.get(tuple(parts), []) if len(parts) == 2 else []
        status = ("ambiguous-declaration-class" if candidates and declaration_names[function["path"]] > 1 else
                  "ambiguous-native-class-prefix" if len({r["class_prefix"] for r in candidates}) > 1 else
                  "unique-static-name-entry" if len(candidates) == 1 else
                  "ambiguous-static-name-entries" if candidates else
                  "static-name-zero-slot" if null_candidates else "no-static-name-entry")
        output.append({key: function[key] for key in
                       ("package", "package_sha256", "export", "path", "native_index", "function_flags")}
                      | {"status": status, "candidates": candidates,
                         "zero_slot_candidates": null_candidates,
                         "package_identity_in_name_table": "absent-not-proven",
                         "native_class_prefix_binding": "not-proven-by-UFunction",
                         "runtime_registration": "not-executed",
                         "compatible_pc_implementation": "not-established"})
    return output


def recover_initializers(image, entries, base=BASE):
    """Decode one exact 31-instruction registration-ctor template.

    The source slot is read from the original image, never guessed from index.
    Different instruction templates remain unsupported instead of emulated.
    """
    fixed = {0: 0x3D608328, 1: 0x3D408325, 2: 0x390A0D80,
             3: 0x814BB660, 4: 0x2F0A0000, 5: 0x409A0028,
             6: 0x39401000, 7: 0x39200001, 8: 0x3CE08250,
             9: 0x912BB660, 10: 0x3968FFFC, 11: 0x38E75980,
             12: 0x7D4903A6, 13: 0x94EB0004, 14: 0x4200FFFC,
             15: 0x3D408250, 17: 0x392A5980, 18: 0x7F0B4840,
             19: 0x419A0020, 21: 0x3D208326, 24: 0x91693F1C,
             26: 0x4E800020, 30: 0x4E800020}
    result = []
    signature = struct.pack(">III", fixed[0], fixed[1], fixed[2])
    for match in re.finditer(re.escape(signature), image):
        offset = match.start()
        if offset % 4 or offset+124 > len(image) or base+offset not in entries:
            continue
        words = struct.unpack_from(">31I", image, offset)
        if any(words[i] != word for i, word in fixed.items()):
            continue
        if words[22] >> 16 != 0x3960:
            continue
        index = words[22] & 0xFFFF
        if index >= 4096 or words[16] != 0x81680000 | index*4 or words[25] != 0x91480000 | index*4 or words[29] != 0x91680000 | index*4:
            continue
        if words[20] >> 16 != 0x3D40 or words[27] >> 16 != 0x3D60 or words[23] >> 16 != 0x814A or words[28] >> 16 != 0x816B:
            continue
        def signed(value):
            return value-0x10000 if value & 0x8000 else value
        source = (((words[20] & 0xFFFF) << 16)+signed(words[23] & 0xFFFF)) & 0xFFFFFFFF
        source_again = (((words[27] & 0xFFFF) << 16)+signed(words[28] & 0xFFFF)) & 0xFFFFFFFF
        if source != source_again or not 0 <= source-base <= len(image)-4:
            continue
        target = struct.unpack_from(">I", image, source-base)[0]
        if target not in entries:
            continue
        result.append({"initializer": base+offset, "native_index": index,
                       "source_pointer_slot": source, "implementation": target,
                       "destination": GNATIVES+index*4,
                       "initialization_flag": 0x8327B660, "fallback": 0x82505980,
                       "table_entries": 4096, "duplicate_index_slot": 0x83263F1C,
                       "instruction_sha256": digest(image[offset:offset+124]),
                       "status": "verified-instruction-template-not-executed"})
    return result


def generated_entries(path):
    data = Path(path).read_bytes()
    text = data.decode("utf-8-sig", errors="strict")
    matches = re.findall(r"registrar->SetFunction\(0x([0-9A-Fa-f]+),\s*sub_([0-9A-Fa-f]+)\);", text)
    if not matches or any(a.upper() != b.upper() for a, b in matches):
        raise ValueError("unexpected generated registration template")
    values = [int(a, 16) for a, _ in matches]
    if len(values) != len(set(values)):
        raise ValueError("duplicate generated function entry")
    return set(values), digest(data)


def core_lookup_witness(image):
    """Verify instructions, not a string-only guess, for the Core table lookup.

    lis r11,0x8321 / addi r31,r11,-5088 creates the table. The loop scales
    index by eight, calls the actual comparison function and returns slot +4.
    Hashes preserve the complete inspected instruction range locally.
    """
    start = CORE_LOOKUP-BASE
    words = struct.unpack_from(">30I", image, start)
    expected = {3: 0x3D608321, 5: 0x3BEBEC20, 18: 0x57DD1838,
                26: 0x397F0004, 27: 0x7C7D5A14}
    # Instruction selection is version-locked by the original XEX SHA guard.
    for index, word in expected.items():
        if words[index] != word:
            raise ValueError(f"Core lookup instruction mismatch at +{index*4:X}")
    return {"entry": CORE_LOOKUP, "table": CORE_TABLE, "stride": 8,
            "returns": "address-of-implementation-slot (+4), not a native call",
            "instruction_range_sha256": digest(image[start:start+30*4]),
            "runtime_execution": "not-executed"}


def analyze(image, uf, entries):
    recovered = recover_tables(image, entries, allowed_starts=PACKED_NAME_STARTS)
    declarations = map_declarations(uf, recovered["tables"], recovered["static_zero_slots"])
    initializers = recover_initializers(image, entries)
    for declaration in declarations:
        declaration["indexed_initializers"] = [i for i in initializers if declaration["native_index"] and i["native_index"] == declaration["native_index"] and i["implementation"] in {r["implementation"] for r in declaration["candidates"]}]
    return {"schema_version": 1, "profile": "MC2-name-lookup-static",
            "image_sha256": digest(image), "base": BASE,
            "core_lookup": core_lookup_witness(image), **recovered,
            "indexed_initializers": initializers,
            "declarations": declarations,
            "summary": {"tables": len(recovered["tables"]),
                        "table_records": sum(len(t["records"]) for t in recovered["tables"]),
                        "native_declarations": len(declarations),
                        "recovered_indexed_initializers": len(initializers),
                        "indexed_declarations_with_matching_initializer": sum(bool(d["indexed_initializers"]) for d in declarations),
                        "mapping_statuses": dict(Counter(d["status"] for d in declarations)),
                        "indexed_mapping_statuses": dict(Counter(d["status"] for d in declarations if d["native_index"])),
                        "runtime_registration": "not-executed", "runtime_gnatives_address": GNATIVES,
                        "runtime_gnatives_initialization": "instruction-template-recovered-not-executed",
                        "compatible_pc_implementations": 0}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xex", type=Path, required=True)
    parser.add_argument("--loader-source", type=Path, required=True)
    parser.add_argument("--ufunction-report", type=Path, required=True)
    parser.add_argument("--generated-register", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = (args.xex, args.loader_source, args.ufunction_report, args.generated_register)
    if any(args.output.resolve() == p.resolve() or (args.output.exists() and args.output.samefile(p)) for p in inputs):
        raise ValueError("output aliases input")
    hashes = {str(p): digest(p.read_bytes()) for p in inputs}
    if hashes[str(args.generated_register)] != REGISTER_SHA256:
        raise ValueError("unsupported generated registration witness hash")
    if hashes[str(args.ufunction_report)] != UFUNCTION_SHA256:
        raise ValueError("unsupported or incomplete UFunction report hash")
    data = args.xex.read_bytes()
    entries, registration_hash = generated_entries(args.generated_register)
    uf = json.loads(args.ufunction_report.read_text(encoding="utf-8-sig"))
    result = analyze(image_from_xex(data, args.loader_source), uf, entries)
    result["inputs"] = hashes
    result["generated_register_sha256"] = registration_hash
    result["generated_entries"] = len(entries)
    result["inputs_unchanged"] = all(digest(p.read_bytes()) == hashes[str(p)] for p in inputs)
    if not result["inputs_unchanged"]:
        raise ValueError("input identity changed during analysis")
    write_json_atomic(args.output, result)
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
