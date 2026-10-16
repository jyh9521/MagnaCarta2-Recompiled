"""Validate and rerun real native initializers and Add on a fully linked host.

Original vtable data words are reproduced in controlled memory, not GNatives.
Initializer, operand, and arithmetic implementations execute unchanged code.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from tools.research.compile_module import digest, inventory
from tools.research.link_module import NATIVE_GENERATED_TREE, runtime_path
from tools.research.verify_branch_ranges import BASE, image_from_xex

ADD_INDEX = 146
ADD_ADDRESS = 0x8250BAF0
OPERAND_ADDRESS = 0x82508E60
OPERAND_SHA256 = 'bead6bd612e03adfd486b56117ba78183689901cf6ce08bbba67131b1ac6fcab'
INITIALIZERS = {
    0x82E707C8: (124, '0f22ced9d1cba6d21c397df528b2ec54899a946468b5fff98efdad68aa92219a'),
    0x82E73108: (124, 'b253452ee0b71cf128edacfd7908079c79026590b4d21f7e851605688b48f4ee'),
}
CASES = ((7, 35), (0, 0), (0xFFFFFFFF, 1), (0x80000000, 0xFFFFFFFF),
         (0x7FFFFFFF, 1), (0xFFFFFFFE, 0xFFFFFFFD),
         (0x12345678, 0x11111111), (0x80000000, 0x80000000))


def native_evidence(image):
    name = 'intUObjectexecAdd_IntInt'.encode('utf-16-be') + b'\0\0'
    expected_name = 0x82157100
    offset = expected_name - BASE
    if image[offset:offset + len(name)] != name:
        raise ValueError('native name identity mismatch')
    pair = struct.pack('>II', expected_name, ADD_ADDRESS)
    if image[0x8320F1E8 - BASE:0x8320F1E8 - BASE + 8] != pair:
        raise ValueError('native name-to-implementation pair mismatch')
    code = image[OPERAND_ADDRESS - BASE:OPERAND_ADDRESS - BASE + 64]
    if hashlib.sha256(code).hexdigest() != OPERAND_SHA256:
        raise ValueError('operand implementation identity mismatch')
    for address in (0x8320B718, 0x8320B728):
        if image[address - BASE:address - BASE + 4] != struct.pack('>I', OPERAND_ADDRESS):
            raise ValueError('operand vtable reference mismatch')
    if image[0x8320B828 - BASE:0x8320B828 - BASE + 4] != struct.pack('>I', ADD_ADDRESS):
        raise ValueError('Add vtable reference mismatch')
    for address, (size, expected) in INITIALIZERS.items():
        if hashlib.sha256(image[address - BASE:address - BASE + size]).hexdigest() != expected:
            raise ValueError('original native initializer identity mismatch')
    return {'name': 'intUObjectexecAdd_IntInt', 'name_address': expected_name,
            'name_pair_address': 0x8320F1E8, 'implementation_address': ADD_ADDRESS,
            'operand_address': OPERAND_ADDRESS, 'operand_code_sha256': OPERAND_SHA256,
            'operand_references': [0x8320B718, 0x8320B728],
            'operand_identity': 'real generated four-byte decoder, execution verified',
            'initializers': {f'{a:08X}': {'size': v[0], 'sha256': v[1]} for a, v in INITIALIZERS.items()},
            'token_binding': 'original initializer 82E707C8 executed: GNatives[0x1D]=82508E60',
            'native_binding': 'original initializer 82E73108 executed: GNatives[146]=8250BAF0',
            'static_data_fixture': 'two original vtable words recreated; no GNatives slot manually written',
            'table_initialization': 'original 4096 fallback fill and guard, two registrations, duplicate path',
            'complete_startup': 'NOT TESTED'}


def declaration_evidence(report):
    matches = [f for f in report.get('functions', []) if
               f.get('package') == 'Core.xxx' and f.get('path') == 'Object.Add_IntInt']
    if len(matches) != 1 or not matches[0].get('is_native') or matches[0].get('native_index') != ADD_INDEX:
        raise ValueError('expected unique native Core.Object.Add_IntInt index 146')
    item = matches[0]
    return {key: item[key] for key in ('package', 'path', 'native_index', 'package_sha256', 'payload_sha256')}


def expected_lines():
    lines = ['NATIVE_INITIALIZERS operand=82E707C8 add=82E73108 guard=1 fallback_slots=4094 duplicate_index=29 success=1']
    lines += [f'NATIVE_CASE {n} lhs={a:08X} rhs={b:08X} result={(a+b)&0xFFFFFFFF:08X} '
             'code_advance=11 restored=1 guards=1 script_unchanged=1 success=1'
             for n, (a, b) in enumerate(CASES)]
    lines.extend(('NATIVE_ADD cases=8 index=146 target=8250BAF0 operand=82508E60 fixture_released=1 status=0',
                  'NATIVE_PROBE status=0'))
    return lines


def validate_output(text, runtime_dll=None):
    actual = [line for line in text.splitlines() if line.startswith('NATIVE_')]
    if actual != expected_lines():
        raise ValueError('native output differs from all eight expected cases and cleanup')
    for marker in ('SETUP status=00000000', 'REGISTRATION count=58408 base=mapped', 'SHUTDOWN complete'):
        if text.splitlines().count(marker) != 1:
            raise ValueError('missing or duplicate host lifecycle marker')
    if runtime_dll is not None:
        actual_dlls = [line[len('RUNTIME_DLL '):] for line in text.splitlines() if line.startswith('RUNTIME_DLL ')]
        if len(actual_dlls) != 1 or Path(actual_dlls[0]).resolve() != Path(runtime_dll).resolve():
            raise ValueError('loaded runtime DLL path mismatch')
    return actual


def verify_host(directory, probe_source, sdk=None):
    directory = Path(directory).resolve()
    report = json.loads((directory / 'host-link.json').read_text(encoding='utf-8'))
    inputs = json.loads((directory / 'inputs.json').read_text(encoding='utf-8'))
    if not report.get('success') or not report.get('inputs_unchanged') or report.get('object_count') != 197:
        raise ValueError('expected successful unchanged full 197-object host')
    if report.get('expected_mappings') != 58408:
        raise ValueError('unexpected full-module mapping count')
    if report.get('native_profile_generated_tree') != NATIVE_GENERATED_TREE:
        raise ValueError('unsupported native generated-tree profile')
    source = Path(probe_source).resolve()
    if inputs.get('input_hashes', {}).get(str(source)) != digest(source):
        raise ValueError('native harness source was not linked with this identity')
    for path, expected in inputs.get('input_hashes', {}).items():
        if digest(path) != expected:
            raise ValueError('linked host input identity changed: ' + Path(path).name)
    sdk_input = inputs.get('sdk')
    if sdk is not None:
        if inventory(Path(sdk).resolve()) != sdk_input:
            raise ValueError('SDK tree identity changed')
        for key in ('generated', 'compiler_resource_headers'):
            item = inputs.get(key)
            if not item or inventory(item['root']) != item:
                raise ValueError(key + ' tree identity changed')
        if inputs['generated']['tree_sha256'] != NATIVE_GENERATED_TREE:
            raise ValueError('native generated tree profile mismatch')
    exe = directory / 'module_probe.exe'
    if digest(exe) != report.get('module_probe.exe', {}).get('sha256'):
        raise ValueError('host executable hash mismatch')
    if not report.get('records') or any(r.get('exit_status') != 0 for r in report['records']):
        raise ValueError('host command failed')
    return exe, report


def run_host(command, output, env):
    try:
        run = subprocess.run(command, cwd=output, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=120, check=False)
        status, stdout, stderr = run.returncode, run.stdout, run.stderr
    except subprocess.TimeoutExpired as exc:
        def text(value):
            return value.decode('utf-8', 'replace') if isinstance(value, bytes) else value or ''
        status, stdout, stderr = 124, text(exc.stdout), text(exc.stderr) + '\nNATIVE_CALL_TIMEOUT seconds=120\n'
    except OSError as exc:
        status, stdout, stderr = 127, '', str(exc) + '\n'
    (output / 'run.txt').write_text(stdout + stderr, encoding='utf-8')
    return status, stdout, stderr


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('host-dir', 'sdk', 'xex', 'loader-source', 'ufunction-report', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--probe-source', type=Path, default=Path('src/host/native_add_probe.cpp'))
    args = parser.parse_args(argv)
    output = args.output.resolve()
    for root in (args.host_dir.resolve(), args.sdk.resolve(), args.probe_source.resolve().parent):
        if output == root or root in output.parents:
            raise ValueError('output must be outside input trees')
    exe, host_report = verify_host(args.host_dir, args.probe_source, args.sdk)
    evidence = native_evidence(image_from_xex(args.xex.read_bytes(), args.loader_source))
    declaration = declaration_evidence(json.loads(args.ufunction_report.read_text(encoding='utf-8')))
    output.mkdir(parents=True, exist_ok=False)
    import os
    command = [str(exe)]
    status, stdout, stderr = run_host(command, output, runtime_path(os.environ, args.sdk.resolve()))
    error = None
    try:
        validate_output(stdout, args.sdk.resolve() / 'bin/rexruntime.dll')
    except ValueError as exc:
        error = str(exc)
    unchanged = True
    try:
        verify_host(args.host_dir, args.probe_source, args.sdk)
    except (ValueError, OSError) as exc:
        unchanged, error = False, str(exc)
    result = {'schema': 1, 'command': command, 'cwd': str(output), 'stdin': 'DEVNULL',
              'exit_status': status, 'literal_stdout': stdout, 'literal_stderr': stderr,
              'error': error, 'success': status == 0 and error is None,
              'executable_sha256': digest(exe), 'harness_source_sha256': digest(args.probe_source),
              'host_report_sha256': digest(args.host_dir / 'host-link.json'),
              'ufunction_report_sha256': digest(args.ufunction_report),
              'xex_sha256': digest(args.xex), 'native_evidence': evidence, 'declaration': declaration,
              'case_count': len(CASES), 'full_module_object_count': host_report['object_count'],
              'host_inputs_unchanged': unchanged,
              'synthetic_memory': True, 'operand_decoder_stub': False,
              'guest_entrypoint_launched': False, 'game_vm_startup': 'NOT TESTED', 'game_boot': 'NOT TESTED'}
    (output / 'native-call.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'NATIVE_CALL cases={len(CASES)} full_module_objects=197 exit={status} success={result["success"]}')
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
