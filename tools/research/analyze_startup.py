"""Hash-locked, read-only XEX startup-chain/table audit; not an emulator."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from tools.formats.xex import parse_xex
from tools.formats.coalesced import write_json_atomic
from tools.research.verify_branch_ranges import BASE, image_from_xex
from tools.research.native_registration import generated_entries, recover_initializers, REGISTER_SHA256

CODE_RANGES = {
    0x82868EC0: (440, 'e0eb1b150ebee9219a51d3546fe9b2e6ccaf504ce0bad69978aa97696ca976c1'),
    0x82869F80: (120, '14a8fedc6b0c3978233a44ec69541e0025e09d52b962f83234d8f826ba24c785'),
    0x82869EA0: (224, '53211e50c3be826d07b0d90681d742ff1c208f2633e3f5f45ccded7869530150'),
    0x8286A0D0: (208, '2355981531669a179c61a164e8ca0ebc5345bded86c4756c4fa34ed1cae387ff'),
}
TABLES = (
    ('pre_c', 0x82EA0000, 0x82EA000C, True),
    ('pre_cpp', 0x831ECAB8, 0x831ECAC4, True),
    ('cpp', 0x82EA0010, 0x831ECAB4, False),
)
# Verified against phase3/module-modified/inputs.json generated.files and files.
GENERATED_INIT_SHA256 = '8fbf9073bfcff48476df7335f7f296c89ab092d4b8af9b85cfdf348de377ac1a'
GENERATED_ENTRY_SHA256 = '9c08b277fa287917337d5a1c9e65d7d363e8675f6d6568c76279ffe24eb896af'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def view(image, address, size, base=BASE):
    offset = address-base
    if size < 0 or offset < 0 or offset+size > len(image):
        raise ValueError('image range out of bounds')
    return image[offset:offset+size]


def direct_calls(code, address):
    """Decode only opcode18 with LK=1, including sign and absolute bit.

    This is a lexical instruction-range audit, not reachable-path inference.
    """
    if address % 4 or len(code) % 4:
        raise ValueError('unaligned instruction range')
    result = []
    for offset in range(0, len(code), 4):
        word = struct.unpack_from('>I', code, offset)[0]
        if word >> 26 != 18 or not word & 1:
            continue
        delta = word & 0x3FFFFFC
        if delta & 0x2000000:
            delta -= 0x4000000
        result.append({'site': address+offset,
                       'target': (delta if word & 2 else address+offset+delta) & 0xFFFFFFFF})
    return result


def pointer_table(image, start, end, entries, base=BASE, skip_minus_one=True):
    if start % 4 or end % 4 or end < start:
        raise ValueError('invalid table bounds')
    data = view(image, start, end-start, base)
    pointers = []
    for index, (value,) in enumerate(struct.iter_unpack('>I', data)):
        if value == 0 or (skip_minus_one and value == 0xFFFFFFFF):
            continue
        if value not in entries:
            raise ValueError(f'initializer target is not a generated boundary: {value:08X}')
        pointers.append({'slot': start+index*4, 'target': value})
    return {'start': start, 'end_exclusive': end, 'slots': len(data)//4,
            'nonzero_count': len(pointers), 'sha256': sha(data), 'pointers': pointers}


def pe_entry(image, base=BASE):
    if len(image) < 64 or image[:2] != b'MZ':
        raise ValueError('invalid DOS header')
    offset = struct.unpack_from('<I', image, 0x3C)[0]
    if offset+44 > len(image) or image[offset:offset+4] != b'PE\0\0':
        raise ValueError('invalid PE header')
    if struct.unpack_from('<H', image, offset+24)[0] != 0x10B:
        raise ValueError('expected PE32')
    rva = struct.unpack_from('<I', image, offset+40)[0]
    view(image, base+rva, 4, base)
    return base+rva


def generated_entry_witness(text, expected_calls):
    """Lexical cross-check only; CLI separately guards complete source hashes."""
    matches = re.findall(r'DEFINE_REX_FUNC\(xstart\) \{(.*?)\n\}',text,re.S)
    if len(matches) != 1:
        raise ValueError('expected one real generated xstart body')
    calls = [int(v,16) for v in re.findall(r'// bl 0x([0-9a-fA-F]+)\s*\n',matches[0])]
    if calls != [c['target'] for c in expected_calls]:
        raise ValueError('generated entry calls differ from original PPC')
    return {'symbol':'xstart', 'body_sha256':sha(matches[0].encode()),
            'direct_calls_match_original':True, 'runtime_execution':'not-executed-by-this-tool'}


def analyze(image, metadata, entries, mapping_text, entry_text):
    entry = next(h['value'] for h in metadata['optional_headers'] if h['name'] == 'entry_point')
    if entry != 0x82868EC0 or pe_entry(image) != entry:
        raise ValueError('XEX/PE entry mismatch or unsupported entry')
    mapping = re.findall(r'\{\s*0x82868EC0\s*,\s*(\w+)\s*\}', mapping_text)
    if mapping != ['xstart']:
        raise ValueError('unsupported title entry mapping')
    code = []
    for address, (size, expected) in CODE_RANGES.items():
        data = view(image, address, size)
        if sha(data) != expected:
            raise ValueError(f'startup instruction hash mismatch: {address:08X}')
        code.append({'address': address, 'size': size, 'sha256': expected,
                     'direct_calls_lexical': direct_calls(data, address)})
    tables = []
    for name, start, end, returns_status in TABLES:
        table = pointer_table(image, start, end, entries, skip_minus_one=not returns_status)
        tables.append(dict(table, role=name, stop_on_nonzero_return=returns_status))
    initializers = recover_initializers(image, entries)
    native_set = {record['initializer'] for record in initializers}
    cpp = tables[2]
    matches = [dict(p, **next({k:v for k,v in r.items() if k != 'initializer'}
                            for r in initializers if r['initializer'] == p['target']))
               for p in cpp['pointers'] if p['target'] in native_set]
    if len(matches) != len(native_set) or len(native_set) != 299:
        raise ValueError('native initializer/table coverage mismatch')
    imports = []
    for slot in (0x82000708, 0x82000710):
        owners = [lib['name'] for lib in metadata['import_libraries'] if slot in lib['import_record_addresses']]
        if len(owners) != 1:
            raise ValueError('expected unique import-library membership')
        raw = struct.unpack('>I', view(image, slot, 4))[0]
        imports.append({'slot': slot, 'raw_word': raw, 'library': owners[0],
                        'ordinal': raw & 0xFFFF, 'type': raw >> 24,
                        'state': 'unbound descriptor, not a valid runtime pointer'})
    gnatives = view(image, 0x83250D80, 4096*4)
    if gnatives != bytes(len(gnatives)):
        raise ValueError('unexpected pre-initialization GNatives data')
    witness = generated_entry_witness(entry_text,code[0]['direct_calls_lexical'])
    return {'schema_version': 1, 'evidence': 'static-only; no title/constructor execution',
            'image_sha256': sha(image), 'xex_entry': entry, 'pe_entry': pe_entry(image),
            'generated_entry_mapping': 'xstart', 'original_entry_body_generated': True,
            'generated_entry_witness':witness,
            'tls': next(h['decoded'] for h in metadata['optional_headers'] if h['name'] == 'tls_info'),
            'stack_size': next(h['value'] for h in metadata['optional_headers'] if h['name'] == 'default_stack_size'),
            'code_ranges': code, 'initializer_tables': tables,
            'native_table_members': matches, 'native_initializer_count': len(matches),
            'imports_before_binding': imports,
            'original_static_values': {f'{a:08X}': struct.unpack('>I', view(image,a,4))[0]
                                       for a in (0x8320B718,0x8320B728,0x8320B828)},
            'gnatives': {'address':0x83250D80, 'slots':4096, 'all_zero':True, 'sha256':sha(gnatives)},
            'first_dependency': {'caller':0x8286A1A0, 'callee':0x8286A0D0,
                                 'import_slot':0x82000708, 'next_dereference':0x10193,
                                 'status':'static candidate, execution must independently verify'}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('xex','loader-source','generated-register','generated-init','generated-entry','output'):
        parser.add_argument('--'+option, type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = (args.xex,args.loader_source,args.generated_register,args.generated_init,args.generated_entry)
    if any(args.output.resolve() == p.resolve() or
           (args.output.exists() and args.output.samefile(p)) for p in inputs):
        raise ValueError('output aliases input')
    hashes = {str(p):sha(p.read_bytes()) for p in inputs}
    if hashes[str(args.generated_register)] != REGISTER_SHA256:
        raise ValueError('unsupported generated registration witness')
    if hashes[str(args.generated_init)] != GENERATED_INIT_SHA256:
        raise ValueError('unsupported generated image-mapping witness')
    if hashes[str(args.generated_entry)] != GENERATED_ENTRY_SHA256:
        raise ValueError('unsupported generated title-entry witness')
    entries, _ = generated_entries(args.generated_register)
    raw = args.xex.read_bytes()
    report = analyze(image_from_xex(raw,args.loader_source),parse_xex(raw),entries,
                     args.generated_init.read_text(encoding='utf-8-sig'),
                     args.generated_entry.read_text(encoding='utf-8-sig'))
    report['inputs'] = hashes
    report['inputs_unchanged'] = all(sha(p.read_bytes()) == hashes[str(p)] for p in inputs)
    if not report['inputs_unchanged']:
        raise ValueError('input changed during analysis')
    write_json_atomic(args.output,report)
    print('STARTUP entry=82868EC0 mapping=xstart cpp_initializers=3873 native_members=299 static_only=1')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
