"""Compile every generated ReXGlue C++ TU; preserve failures and input identities.

This produces COFF objects, not a linked game or proof of PPC semantics.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

from tools.research.probe_route_a import CLANG_CL_SHA256


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def inventory(root):
    root = Path(root)
    files = {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob('*')) if p.is_file()}
    if not files:
        raise ValueError(f'empty input tree: {root}')
    identity = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'root': str(root.resolve()), 'tree_sha256': identity, 'files': files}


def command(compiler, sdk, generated, source, obj):
    return [str(compiler), '/nologo', '/c', '/Brepro', '/std:c++latest', '/utf-8',
            '/fp:strict', '/DSPDLOG_FMT_EXTERNAL', '/DSPDLOG_COMPILED_LIB', '/DNOMINMAX',
            '/DWIN32_LEAN_AND_MEAN', '/EHa', '/arch:AVX2', '/bigobj', '/MD',
            '/I' + str(sdk / 'include'), '/I' + str(generated), str(source), '/Fo' + str(obj)]


def compile_one(compiler, sdk, generated, source, output, env, timeout):
    obj, log = output / 'objects' / (source.stem + '.obj'), output / 'logs' / (source.name + '.txt')
    argv = command(compiler, sdk, generated, source, obj)
    record = {'source': source.name, 'source_sha256': digest(source), 'command': argv,
              'stdin': 'DEVNULL', 'log': str(log), 'object': str(obj)}
    started = time.monotonic()
    with log.open('x', encoding='utf-8') as stream:
        try:
            record['exit_status'] = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL,
                stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, check=False).returncode
        except subprocess.TimeoutExpired:
            stream.write(f'\nMODULE_COMPILE_TIMEOUT seconds={timeout}\n')
            record['exit_status'] = 124
        except OSError as exc:
            stream.write(str(exc) + '\n')
            record['exit_status'] = 127
    record['elapsed_seconds'] = round(time.monotonic() - started, 3)
    record['log_sha256'] = digest(log)
    if obj.is_file():
        record['object_sha256'], record['object_size'] = digest(obj), obj.stat().st_size
    record['success'] = record['exit_status'] == 0 and obj.is_file() and obj.stat().st_size > 0
    with (output / 'logs' / (source.name + '.json')).open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
    print(f"TU {source.name} exit={record['exit_status']} object={record['success']}", flush=True)
    return record


def vc_environment(vcvars):
    # Keep installed compiler/SDK configuration process-local; do not change PATH globally.
    result = subprocess.run(f'cmd.exe /d /s /c "call \"{vcvars}\" >nul && set"',
        capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(f'vcvars failed: exit={result.returncode}: {result.stderr}')
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line and not line.startswith('='))


def build(generated, sdk, compiler, output, env, jobs=2, timeout=600):
    generated, sdk, compiler, output = map(lambda p: Path(p).resolve(), (generated, sdk, compiler, output))
    if not 1 <= jobs <= 4 or timeout < 1:
        raise ValueError('jobs must be 1..4 and timeout must be positive')
    if digest(compiler) != CLANG_CL_SHA256:
        raise ValueError('Clang compiler SHA-256 mismatch')
    sources = sorted(generated.glob('*.cpp'))
    if not sources:
        raise ValueError('no generated C++ translation units')
    cmake = generated / 'sources.cmake'
    if cmake.is_file():
        declared = re.findall(r'\$\{CMAKE_CURRENT_LIST_DIR\}/([A-Za-z0-9_.-]+\.cpp)', cmake.read_text(encoding='utf-8'))
        if len(declared) != len(set(declared)) or set(declared) != {p.name for p in sources}:
            raise ValueError('sources.cmake does not match generated C++ inventory')
    # Identity includes headers, stamps and SDK headers used transitively.
    before, sdk_before = inventory(generated), inventory(sdk / 'include')
    resource_dir = compiler.parent.parent / 'lib' / 'clang' / '20' / 'include'
    resource_before = inventory(resource_dir) if resource_dir.is_dir() else None
    if output == generated or generated in output.parents or output == sdk or sdk in output.parents:
        raise ValueError('output must be outside input trees')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'objects').mkdir()
    (output / 'logs').mkdir()
    metadata = {'schema': 1, 'floating_point_contract': 'strict', 'generated': before, 'sdk_include': sdk_before,
                'compiler': str(compiler), 'compiler_sha256': digest(compiler),
                'compiler_resource_headers': resource_before,
                'jobs': jobs, 'per_tu_timeout_seconds': timeout, 'expected_tus': len(sources),
                'toolchain_environment': {k: v for k, v in env.items() if k.upper() in
                    ('INCLUDE', 'LIB', 'VCTOOLSVERSION', 'WINDOWSSDKVERSION', 'VCTOOLSINSTALLDIR', 'WINDOWSSDKDIR')}}
    (output / 'inputs.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        records = list(pool.map(lambda source: compile_one(compiler, sdk, generated, source, output, env, timeout), sources))
    stable = inventory(generated) == before and inventory(sdk / 'include') == sdk_before and digest(compiler) == CLANG_CL_SHA256
    if resource_before is not None:
        stable = stable and inventory(resource_dir) == resource_before
    passed = sum(r['success'] for r in records)
    summary = {'schema': 1, 'expected_tus': len(sources), 'attempted_tus': len(records),
               'successful_tus': passed, 'failed_tus': len(records) - passed,
               'inputs_unchanged': stable, 'records': records, 'linked_game': False,
               'game_execution': 'NOT TESTED', 'success': passed == len(sources) and stable}
    (output / 'module-build.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(f'MODULE_COMPILE expected={len(sources)} attempted={len(records)} passed={passed} failed={len(records)-passed} inputs_unchanged={stable}', flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('generated', 'sdk', 'compiler', 'vcvars', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args(argv)
    try:
        if os.name != 'nt':
            raise ValueError('real module compilation requires Windows and VS x64 environment')
        env = vc_environment(args.vcvars.resolve())
        result = build(args.generated, args.sdk, args.compiler, args.output, env, args.jobs, args.timeout)
        return 0 if result['success'] else 1
    except (OSError, ValueError) as exc:
        print(f'MODULE_COMPILE_ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
