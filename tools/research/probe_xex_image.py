"""Load the hash-locked XEX through the SDK, verify all original image bytes, run Add.

No static vtable/GNatives fixture is written. Only call argument memory is synthetic.
The local snapshot contains original data and must never be redistributed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import struct
import sys

from tools.research.compile_module import digest, inventory, vc_environment
from tools.research.link_module import build, validate_native_profile
from tools.research.probe_native_call import expected_lines, native_evidence
from tools.research.verify_branch_ranges import BASE, image_from_xex
from tools.formats.xex import parse_xex


def image_layout(image):
    if len(image) < 0x40 or image[:2] != b'MZ':
        raise ValueError('invalid image DOS header')
    pe = struct.unpack_from('<I', image, 0x3C)[0]
    if pe + 24 > len(image) or image[pe:pe+4] != b'PE\0\0':
        raise ValueError('invalid image PE header')
    count = struct.unpack_from('<H', image, pe+6)[0]
    optional = struct.unpack_from('<H', image, pe+20)[0]
    if not count or count > 96 or optional < 60 or pe+24+optional+count*40 > len(image):
        raise ValueError('invalid section/optional-header bounds')
    if struct.unpack_from('<H', image, pe+24)[0] != 0x10B:
        raise ValueError('expected PE32 image')
    sections = []
    for i in range(count):
        offset = pe+24+optional+i*40
        name = image[offset:offset+8].split(b'\0', 1)[0].decode('ascii', 'strict')
        size, rva, raw_size, raw_offset = struct.unpack_from('<IIII', image, offset+8)
        if rva+size > 0x100000000:
            raise ValueError('section address overflow')
        covered = min(size, max(0, len(image)-rva))
        sections.append({'name': name, 'rva': rva, 'virtual_size': size,
            'raw_size': raw_size, 'raw_offset': raw_offset, 'covered_bytes': covered,
            'coverage': 'complete' if covered == size else 'partial-security-image',
            'sha256': hashlib.sha256(image[rva:rva+covered]).hexdigest()})
    return {'security_image_bytes': len(image),
            'pe_declared_size_of_image': struct.unpack_from('<I', image, pe+24+56)[0],
            'sections': sections}


def import_bindings(text, original, metadata):
    allowed = {}
    for library in metadata['import_libraries']:
        name = library['name'].rsplit('.', 1)[0]
        for address in library['import_record_addresses']:
            offset = address-BASE
            if offset < 0 or offset+4 > len(original):
                raise ValueError('import record outside original image')
            word = struct.unpack_from('>I', original, offset)[0]
            if word >> 24 == 0:
                allowed[(name,address)] = word & 0xffff
    result = []
    for line in text.splitlines():
        if not line.startswith('IMAGE_VARIABLE '):continue
        match = re.fullmatch(r'IMAGE_VARIABLE library=(\w+) ordinal=(\d+) slot=([0-9A-F]{8}) actual=([0-9A-F]{8}) expected=([0-9A-F]{8}) success=1',line)
        if not match:raise ValueError('malformed SDK variable binding')
        library, ordinal, address, actual, expected = match.groups()
        ordinal,address,actual,expected=int(ordinal),int(address,16),int(actual,16),int(expected,16)
        if allowed.get((library,address)) != ordinal or actual != expected or not actual:
            raise ValueError('SDK variable binding not backed by original import/resolver')
        result.append({'library':library,'ordinal':ordinal,'address':address,'value':actual})
    if len(result)!=13 or len({r['address'] for r in result})!=13:
        raise ValueError('expected thirteen distinct SDK variable bindings')
    expected_ordinals={14,27,89,173,342,344,403,430,446,447,448,449,614}
    if {r['ordinal'] for r in result}!=expected_ordinals or any(r['library']!='xboxkrnl' for r in result):
        raise ValueError('unsupported variable import profile')
    return result


def compare_loaded(original, loaded, bindings=()):
    if len(loaded) != len(original):
        raise ValueError('SDK snapshot security-image size mismatch')
    layout = image_layout(original)
    normalized=bytearray(loaded)
    for binding in bindings:
        offset=binding['address']-BASE
        if offset<0 or offset+4>len(original):raise ValueError('variable slot outside image')
        if struct.unpack_from('>I',loaded,offset)[0]!=binding['value']:
            raise ValueError('loaded variable differs from SDK resolver')
        normalized[offset:offset+4]=original[offset:offset+4]
    if original != normalized:
        first = next(i for i, (a, b) in enumerate(zip(original, normalized)) if a != b)
        raise ValueError(f'loaded image differs from original at {BASE+first:08X}')
    differences=sum(a!=b for a,b in zip(original,loaded))
    for section in layout['sections']:
        rva,size=section['rva'],section['covered_bytes']
        section['loaded_sha256']=hashlib.sha256(loaded[rva:rva+size]).hexdigest()
        section['different_bytes']=sum(a!=b for a,b in zip(original[rva:rva+size],loaded[rva:rva+size]))
    return {**layout, 'compared_bytes': len(original), 'different_bytes':differences,
            'unexplained_different_bytes':0, 'SDK_variable_bindings':list(bindings),
            'original_sha256': hashlib.sha256(original).hexdigest(),
            'loaded_sha256': hashlib.sha256(loaded).hexdigest(),
            'partial_section_policy': 'Only bytes inside security/basic image compared; no complete .reloc claim'}


def validate_image_output(text, runtime_dll):
    lines = text.splitlines()
    native = [line for line in lines if line.startswith('NATIVE_')]
    if native != expected_lines():
        raise ValueError('native initializers/eight cases differ')
    required = ['SETUP status=00000000', 'REGISTRATION count=58408 base=mapped',
        'IMAGE_LOAD path=game:\\default-disc1.xex status=00000000',
        'IMAGE_MODULE entry=82868EC0 stack=00040000',
        'IMAGE_SNAPSHOT base=82000000 size=20119552',
        'IMAGE_VTABLE operand=82508E60 add=8250BAF0 original=1',
        'IMAGE_GNATIVES zero_slots=4096',
        'IMAGE_SIZES security=20119552 pe_declared=22284288 sdk_pages=20119552',
        'IMAGE_KERNEL tables=3 variables=13',
        'IMAGE_IMPORT library=xam records=91', 'IMAGE_IMPORT library=xboxkrnl records=168',
        'SHUTDOWN complete']
    for line in required:
        if lines.count(line) != 1:
            raise ValueError('missing or duplicate image marker: '+line)
    dlls = [line[12:] for line in lines if line.startswith('RUNTIME_DLL ')]
    if len(dlls) != 1 or Path(dlls[0]).resolve() != Path(runtime_dll).resolve():
        raise ValueError('runtime DLL identity mismatch')
    return required


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build-dir', 'generated', 'sdk', 'compiler', 'vcvars', 'xex', 'loader-source', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path('src/host/image_probe.cpp'))
    args = parser.parse_args(argv)
    if os.name != 'nt':
        raise ValueError('real SDK probe requires Windows')
    validate_native_profile(inventory(args.generated.resolve()))
    image = image_from_xex(args.xex.read_bytes(), args.loader_source)
    original_native = native_evidence(image)
    before = {str(p.resolve()): digest(p) for p in (args.xex, args.loader_source, args.source)}
    if args.xex.name != 'default-disc1.xex':
        raise ValueError('hash-locked image probe expects default-disc1.xex name')
    out = args.output.resolve()
    for root in (args.xex.resolve().parent, args.loader_source.resolve().parent):
        if out == root or root in out.parents:
            raise ValueError('output must be outside original input trees')
    env = vc_environment(args.vcvars.resolve())
    linker = Path(env['VCToolsInstallDir'])/'bin/Hostx64/x64/link.exe'
    markers = ['SETUP status=00000000', 'REGISTRATION count=58408 base=mapped',
               'NATIVE_PROBE status=0', 'SHUTDOWN complete']
    result = build(args.build_dir, args.generated, args.sdk, args.compiler, linker,
        args.source, out, env, run_environment={'MC2_XEX_PATH': str(args.xex.resolve())},
        expected_markers=markers)
    error, comparison = None, None
    try:
        validate_image_output((out/'run.txt').read_text(encoding='utf-8'),args.sdk/'bin/rexruntime.dll')
        bindings=import_bindings((out/'run.txt').read_text(encoding='utf-8'), image,parse_xex(args.xex.read_bytes()))
        comparison = compare_loaded(image,(out/'loaded-image.bin').read_bytes(),bindings)
        if before != {p:digest(p) for p in before}:
            raise ValueError('original image/probe inputs changed')
    except (ValueError, OSError) as exc:
        error = str(exc)
    report = {'schema':1, 'success': result['success'] and error is None,
        'error':error, 'input_hashes':before, 'original_inputs_unchanged':before == {p:digest(p) for p in before},
        'host_report_sha256':digest(out/'host-link.json'), 'comparison':comparison,
        'native_evidence':original_native,
        'static_data_fixture':False, 'GNatives_fixture':False,
        'synthetic_memory':'only FFrame/script/result/stack call arguments',
        'real_initializer_count':2, 'native_case_count':8,
        'title_entrypoint_launched':False, 'game_boot':'NOT TESTED'}
    report['native_evidence']['static_data_fixture']='none: original SDK-loaded image; only thirteen SDK variable import slots differ before initializers'
    report['native_evidence']['complete_startup']='NOT TESTED; two native initializer calls only'
    (out/'xex-image.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'XEX_IMAGE bytes={len(image)} differences={comparison["different_bytes"] if comparison else "unknown"} native_cases=8 success={report["success"]}')
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
