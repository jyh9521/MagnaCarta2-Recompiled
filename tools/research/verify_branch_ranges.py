"""Verify hash-locked PPC early-return ranges and regenerated control flow.

Key material stays in memory: --loader-source is the original Xenia source at
the commit documented in RESEARCH_BRANCH_FIXES.md; no keys/images are emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.formats.xex import parse_xex
from tools.research.probe_route_a import XEX_SHA256

LOADER_SHA256 = "36a30e1bc54b9854cbd2572b74e366e733460c5df6edf2b29542de36575858f2"
BASE = 0x82000000
RANGES = {
    0x82CE6748: "816302c82b0b0000419a0010896b01d4556307fe4e800020816302c42b0b0000409affec816302cc2b0b0000409affe0386000004e800020",
    0x82DA3488: "816300502b0b0000409a000c386000004e800020816b007c2b0b0000419afff081630050806b007c81430000812a011c7d2903a64e800420",
}
BRANCHES = {0x82CE6768: 0x82CE6754, 0x82CE6774: 0x82CE6754,
            0x82DA34A4: 0x82DA3494}
FUNCLETS = (0x829335B4, 0x82934134, 0x82927154, 0x829183A8, 0x82938758)


def image_from_xex(data, loader_source):
    if hashlib.sha256(data).hexdigest() != XEX_SHA256:
        raise ValueError("unsupported XEX hash")
    source = Path(loader_source).read_bytes()
    if hashlib.sha256(source).hexdigest() != LOADER_SHA256:
        raise ValueError("unsupported loader source hash")
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    # Derive only from the pinned, locally supplied upstream source; never log.
    array = source.decode().split("xe_xex2_retail_key[16] = {")[1].split("}")[0]
    key = bytes(int(v, 16) for v in re.findall(r"0x([0-9a-fA-F]{2})", array))
    def decrypt(key, block):
        decoder = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).decryptor()
        return decoder.update(block) + decoder.finalize()
    meta = parse_xex(data)
    if meta["file_format"]["encryption_type"] != 1 or meta["file_format"]["compression_type"] != 1:
        raise ValueError("expected encrypted basic-block XEX")
    security = meta["security_info_offset"]
    session = decrypt(key, data[security+0x150:security+0x160])
    raw = decrypt(session, data[meta["pe_data_offset"]:])
    image, offset = bytearray(), 0
    for block in meta["file_format"]["basic_blocks"]:
        size = block["data_size"]
        image.extend(raw[offset:offset+size])
        image.extend(bytes(block["zero_size"]))
        offset += size
    if image[:2] != b"MZ" or len(image) != meta["security"]["image_size"]:
        raise ValueError("decoded image size/signature mismatch")
    return bytes(image)


def branch_target(address, word):
    if word >> 26 != 16 or word & 1:
        raise ValueError("expected conditional branch without link")
    displacement = word & 0xFFFC
    if displacement & 0x8000:
        displacement -= 0x10000
    return displacement & 0xFFFFFFFF if word & 2 else (address+displacement) & 0xFFFFFFFF


def verify_image(image):
    for address, expected in RANGES.items():
        data = bytes.fromhex(expected)
        if image[address-BASE:address-BASE+len(data)] != data:
            raise ValueError(f"PPC range mismatch at {address:08X}")
    for address, expected in BRANCHES.items():
        word = struct.unpack_from(">I", image, address-BASE)[0]
        if branch_target(address, word) != expected:
            raise ValueError("branch displacement mismatch")
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    if image[pe:pe+4] != b"PE\0\0":
        raise ValueError("invalid PE header")
    pdata, size = struct.unpack_from("<II", image, pe+24+96+3*8)
    if pdata+size > len(image) or size % 8:
        raise ValueError("invalid PDATA bounds")
    records = {}
    for offset in range(pdata, pdata+size, 8):
        address, fields = struct.unpack_from(">II", image, offset)
        records[address] = ((fields >> 8) & 0x3FFFFF)*4
    for start in FUNCLETS:
        for address, expected in ((start, 0x94), (start+0x9C, 0x54), (start+0xF0, 0x28)):
            if records.get(address) != expected:
                raise ValueError(f"PDATA funclet size mismatch {address:08X}")
    return {"ranges": [f"{a:08X}+38" for a in RANGES], "branches": len(BRANCHES), "pdata_funclets": 15}


def verify_generated(directory):
    files = sorted(Path(directory).glob("*_recomp.*.cpp"))
    functions = {}
    fatal_count = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        fatal_count += text.count("REX_FATAL(")
        for match in re.finditer(r"DEFINE_REX_FUNC\([^\n]+\) \{(.*?)\n\}", text, re.S):
            body = match.group(1)
            labels = set(re.findall(r"^\s*(loc_[A-F0-9]+):", body, re.M))
            missing = set(re.findall(r"goto (loc_[A-F0-9]+);", body))-labels
            if missing:
                raise ValueError(f"undeclared generated labels in {path.name}: {sorted(missing)}")
        for address in RANGES:
            marker = f"DEFINE_REX_FUNC(sub_{address:08X}) {{"
            if marker in text:
                body = text.split(marker, 1)[1].split("\n}\n", 1)[0]
                if address in functions:
                    raise ValueError("duplicate range function")
                functions[address] = body
    if len(functions) != 2:
        raise ValueError("expected both contiguous generated functions")
    for address, body in functions.items():
        if "REX_FATAL" in body or "ERROR:" in body:
            raise ValueError("unresolved branch remains")
        target = 0x82CE6754 if address == 0x82CE6748 else 0x82DA3494
        count = 2 if address == 0x82CE6748 else 1
        condition = "!ctx.cr6.eq" if count == 2 else "ctx.cr6.eq"
        if body.count(f"if ({condition}) goto loc_{target:08X};") != count:
            raise ValueError("expected conditional goto missing")
        if body.count(f"loc_{target:08X}:") != 1:
            raise ValueError("expected shared target label missing")
        forward = 0x82CE6760 if count == 2 else 0x82DA349C
        forward_condition = "ctx.cr6.eq" if count == 2 else "!ctx.cr6.eq"
        if body.count(f"if ({forward_condition}) goto loc_{forward:08X};") != 1:
            raise ValueError("expected forward branch missing")
        if body.count(f"loc_{forward:08X}:") != 1:
            raise ValueError("expected forward target label missing")
    if fatal_count:
        raise ValueError(f"generated module still contains {fatal_count} REX_FATAL calls")
    return {"recompiled_translation_units": len(files),
            "generated_translation_units": len(list(Path(directory).glob("*.cpp"))),
            "verified_gotos": 5, "corrected_gotos": 3, "rex_fatal_calls": fatal_count}


def execute_leaf(code, address, registers, memory, limit=64):
    """Small independent PPC subset oracle, not a general emulator/game runner.

    The caller supplies synthetic memory. Missing reads and unsupported opcodes
    fail instead of inventing an implementation. bctr records a dispatch only.
    """
    pc, equal, ctr, trace = address, False, None, []
    registers = dict(registers)
    for _ in range(limit):
        offset = pc-address
        if offset < 0 or offset+4 > len(code) or offset % 4:
            raise ValueError("PC outside guarded function")
        word = struct.unpack_from(">I", code, offset)[0]
        trace.append(pc)
        op, rt, ra = word >> 26, (word >> 21) & 31, (word >> 16) & 31
        imm = word & 0xFFFF
        signed = imm-0x10000 if imm & 0x8000 else imm
        next_pc = pc+4
        if word == 0x4E800020:
            return {"return": registers.get(3, 0), "dispatch": None, "trace": trace}
        if word == 0x4E800420:
            return {"return": registers.get(3, 0), "dispatch": ctr, "trace": trace}
        if op in (32, 34):
            ea = (registers.get(ra, 0)+signed) & 0xFFFFFFFF
            value = memory[ea]  # deliberate KeyError on an unsupplied fixture read
            registers[rt] = value & (0xFFFFFFFF if op == 32 else 0xFF)
        elif op == 10 and rt == 24:  # cmplwi cr6,ra,imm
            equal = (registers.get(ra, 0) & 0xFFFFFFFF) == imm
        elif op == 16:
            bo, bi = rt, ra
            if bo not in (4, 12) or bi != 26:
                raise ValueError("unsupported branch condition")
            if equal == (bo == 12):
                next_pc = branch_target(pc, word)
        elif op == 14 and ra == 0:  # li
            registers[rt] = signed & 0xFFFFFFFF
        elif op == 21:  # rlwinm: PPC bit numbering is MSB-first
            shift, begin, end = (word >> 11) & 31, (word >> 6) & 31, (word >> 1) & 31
            value = registers.get(rt, 0) & 0xFFFFFFFF
            rotated = ((value << shift) | (value >> ((32-shift) & 31))) & 0xFFFFFFFF
            bits = list(range(begin, end+1)) if begin <= end else list(range(begin, 32))+list(range(end+1))
            mask = sum(1 << (31-bit) for bit in bits)
            registers[ra] = rotated & mask
        elif op == 31 and ((word >> 1) & 1023) == 467 and ((word >> 11) & 1023) == 288:
            ctr = registers.get(rt, 0)  # mtctr SPR encoding
        else:
            raise ValueError(f"unsupported PPC oracle opcode {word:08X}")
        pc = next_pc
    raise ValueError("PPC oracle instruction limit")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xex", type=Path, required=True)
    parser.add_argument("--loader-source", type=Path, required=True)
    parser.add_argument("--generated", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = verify_image(image_from_xex(args.xex.read_bytes(), args.loader_source))
    if args.generated:
        result.update(verify_generated(args.generated))
    result.update(input_sha256=XEX_SHA256, game_execution="NOT TESTED")
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print("BRANCH_RANGES " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
