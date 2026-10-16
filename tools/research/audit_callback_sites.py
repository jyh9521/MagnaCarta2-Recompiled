"""Bounded static lis/addi -> r6 candidates at direct calls; never adds hints.

The real-image CLI accepts only the project's verified original image hash.
The pure scanner supports synthetic fixtures and uses no third-party packages.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct

BASE = 0x82000000
IMAGE_SHA256 = 'd18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9'
TARGET = 0x8286FD30


def signed16(value):
    return value-0x10000 if value & 0x8000 else value


def direct_branch(address, word):
    if word >> 26 != 18:
        return None
    delta = word & 0x3FFFFFC
    if delta & 0x2000000:
        delta -= 0x4000000
    return ((delta if word & 2 else address+delta) & 0xFFFFFFFF, bool(word & 1))


def writes(word):
    """Conservative whitelist; None means unknown effects/control transfer.

    Never infer safety from a guessed destination field on an unknown opcode.
    """
    op, rt, ra = word >> 26, (word >> 21) & 31, (word >> 16) & 31
    if op in (14, 15, 32, 34):  # addi/addis/lwz/lbz, no update forms
        return {rt}
    if op in (36, 38, 48, 50, 52, 54):  # stores or floating loads, no GPR update
        return set()
    if op in (10, 11):
        return set()
    if op in (20, 21, 23, 24, 25, 26, 27, 28, 29):
        return {ra}
    if op == 31:
        xo = (word >> 1) & 1023
        if xo in (444, 316, 28, 60, 124, 284, 412, 476, 24, 536, 792, 824):
            return {ra}
        if xo in (266, 40, 8, 10, 136, 138, 235, 339):
            return {rt}
        if xo in (0, 32):
            return set()
    if op == 63 and (word & 0x7FE) == (72 << 1):  # fmr only
        return set()
    return None


def recover(words, call_index, base, window=16):
    if not 1 <= window <= 64:
        raise ValueError('window must be 1..64 instructions')
    low_index = max(0, call_index-window)
    add_index = None
    for index in range(call_index-1, low_index-1, -1):
        word = words[index]
        effect = writes(word)
        if effect is None:
            return {'status': 'unresolved', 'reason': 'control-or-unknown-effects'}
        if 6 in effect:
            if word >> 26 != 14 or ((word >> 21) & 31) != 6:
                return {'status': 'unresolved', 'reason': 'r6-not-written-by-addi'}
            add_index = index
            break
    if add_index is None:
        return {'status': 'unresolved', 'reason': 'r6-definition-outside-window'}
    add = words[add_index]
    source = (add >> 16) & 31
    if not source:
        return {'status': 'unresolved', 'reason': 'r6-is-immediate-not-lis-addi'}
    for index in range(add_index-1, low_index-1, -1):
        word = words[index]
        effect = writes(word)
        if effect is None:
            return {'status': 'unresolved', 'reason': 'control-or-unknown-effects'}
        if source in effect:
            if word >> 26 != 15 or ((word >> 16) & 31) != 0:
                return {'status': 'unresolved', 'reason': 'source-not-written-by-lis'}
            value = ((signed16(word & 0xFFFF) << 16)+signed16(add & 0xFFFF)) & 0xFFFFFFFF
            # Reject a branch from anywhere in this section into the chain;
            # such entries could bypass the lis/addi data definition.
            begin, end = base+index*4, base+call_index*4
            entries = []
            for origin, other in enumerate(words):
                op = other >> 26
                target = direct_branch(base+origin*4, other)
                if target is not None:
                    destination = target[0]
                elif op == 16:
                    delta = signed16(other & 0xFFFC)
                    destination = (delta if other & 2 else base+origin*4+delta) & 0xFFFFFFFF
                else:
                    continue
                if begin < destination <= end:
                    entries.append(base+origin*4)
            if entries:
                return {'status': 'unresolved', 'reason': 'branch-enters-definition-chain', 'incoming_branches': entries}
            return {'status': 'static-candidate', 'lis': begin, 'addi': base+add_index*4,
                    'target': value, 'source_register': source, 'argument_register': 6,
                    'range_kind': 'caller-address-definition-chain',
                    'callback_body_boundary': 'not-assessed',
                    'range_size': end+4-begin,
                    'range_sha256': hashlib.sha256(struct.pack('>'+str(call_index-index+1)+'I', *words[index:call_index+1])).hexdigest()}
    return {'status': 'unresolved', 'reason': 'lis-outside-window'}


def scan(code, base, target=TARGET, window=16):
    if not 1 <= window <= 64:
        raise ValueError('window must be 1..64 instructions')
    if base < 0 or base % 4 or len(code) % 4 or base+len(code) > 0x100000000:
        raise ValueError('invalid aligned code range')
    words = list(struct.unpack('>'+str(len(code)//4)+'I', code))
    records = []
    for index, word in enumerate(words):
        if direct_branch(base+4*index, word) == (target, True):
            records.append({'call': base+4*index, **recover(words, index, base, window)})
    return records


def executable_sections(image):
    if len(image) < 64 or image[:2] != b'MZ':
        raise ValueError('invalid DOS image')
    pe = struct.unpack_from('<I', image, 0x3C)[0]
    if pe+24 > len(image) or image[pe:pe+4] != b'PE\0\0':
        raise ValueError('invalid PE header')
    count, optional = struct.unpack_from('<H', image, pe+6)[0], struct.unpack_from('<H', image, pe+20)[0]
    if not 0 < count <= 96 or optional < 96 or pe+24+optional+count*40 > len(image):
        raise ValueError('invalid section table')
    result=[]
    for i in range(count):
        offset=pe+24+optional+40*i
        size, rva = struct.unpack_from('<II', image, offset+8)
        flags=struct.unpack_from('<I', image, offset+36)[0]
        if flags & 0x20000000:
            if rva+size>len(image) or size%4 or rva%4:
                raise ValueError('unsupported executable section extent')
            result.append((image[offset:offset+8].split(b'\0',1)[0].decode('ascii'),rva,size))
    return result


def audit(image, generated=None):
    if hashlib.sha256(image).hexdigest() != IMAGE_SHA256:
        raise ValueError('unsupported original image SHA-256')
    records=[]
    for name, offset, size in executable_sections(image):
        records.extend(dict(section=name, **row) for row in scan(image[offset:offset+size],BASE+offset))
    registered=set()
    registration_sha256=None
    if generated is not None:
        text=(Path(generated)/'mc2_probe_register.cpp').read_text(encoding='utf-8')
        registration_sha256=hashlib.sha256((Path(generated)/'mc2_probe_register.cpp').read_bytes()).hexdigest()
        registered={int(x,16) for x in re.findall(r'SetFunction\(0x([0-9A-Fa-f]{8}),',text)}
        for row in records:
            if row['status']=='static-candidate':row['registered']=row['target'] in registered
    return {'image_sha256':IMAGE_SHA256,'callee':TARGET,'window_instructions':16,
            'registration_sha256':registration_sha256,
            'sites':records,'status_counts':dict(Counter(row['status'] for row in records)),
            'runtime_execution':'NOT TESTED','automatic_hints_written':False,
            'limits':'direct bl sites only; bounded local definition chains; unknown effects or incoming branches fail closed; no complete CFG or dynamic function-pointer proof'}


def arguments(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    inputs=p.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--image',type=Path)
    inputs.add_argument('--xex',type=Path)
    p.add_argument('--loader-source',type=Path)
    p.add_argument('--generated',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv)
    if bool(a.xex) != bool(a.loader_source):
        p.error('--xex requires --loader-source; --image must not use --loader-source')
    return a


def main(argv=None):
    a=arguments(argv)
    inputs=[p.resolve() for p in (a.image,a.xex,a.loader_source) if p is not None]
    if a.output.resolve() in inputs:raise ValueError('output overlaps input')
    if a.generated and (a.output.resolve()==a.generated.resolve() or a.generated.resolve() in a.output.resolve().parents):
        raise ValueError('output is inside generated input tree')
    if a.xex:
        # Reuse the pinned XEX/source guards; optional crypto is imported only
        # on this real-input path, never by the standard-library fixture tests.
        from tools.research.verify_branch_ranges import image_from_xex
        image=image_from_xex(a.xex.read_bytes(),a.loader_source)
    else:
        image=a.image.read_bytes()
    result=audit(image,a.generated)
    result['input_mode']='hash-locked-xex-in-memory' if a.xex else 'hash-locked-image'
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as out:json.dump(result,out,indent=2);out.write('\n')
    print('CALLBACK_SITE_AUDIT '+json.dumps(result['status_counts'],sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
