"""Run two exact regenerated leaf bodies on synthetic memory against a PPC oracle.

The only replaced boundary records (does not execute) an indirect guest dispatch.
This is not a game runner, runtime implementation, or whole-game equivalence proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from tools.research.compile_module import digest, vc_environment
from tools.research.probe_route_a import CLANG_CL_SHA256
from tools.research.verify_branch_ranges import RANGES, execute_leaf


def extract_bodies(generated):
    found = {}
    for path in sorted(Path(generated).glob('*.cpp')):
        text = path.read_text(encoding='utf-8')
        for address in RANGES:
            pattern = rf'DEFINE_REX_FUNC\(sub_{address:08X}\) \{{(.*?)\n\}}'
            matches = list(re.finditer(pattern, text, re.S))
            if matches:
                if address in found or len(matches) != 1:
                    raise ValueError('duplicate generated leaf')
                match = matches[0]
                if 'REX_FATAL' in match[0] or 'ERROR:' in match[0]:
                    raise ValueError('unresolved generated leaf')
                found[address] = {'source': str(path.resolve()), 'source_sha256': digest(path),
                                  'body': match[0], 'body_start_line': text.count('\n', 0, match.start())+1,
                                  'body_end_line': text.count('\n', 0, match.end())+1,
                                  'body_sha256': hashlib.sha256(match[0].encode('utf-8')).hexdigest()}
    if len(found) != len(RANGES):
        raise ValueError('expected both generated leaves')
    return found


def cases():
    fixtures = []
    for selected in range(4):
        for flag in (0, 1, 2, 3, 128, 255):
            values = [0x2000 if selected == i else 0 for i in range(3)]
            fixtures.append({'address': 0x82CE6748, 'r3': 0x1000,
                'memory': {0x1000+712: values[0], 0x1000+708: values[1],
                           0x1000+716: values[2], 0x2000+468: flag},
                'byte_addresses': [0x2000+468]})
    for outer, inner in ((0, 0), (0x2000, 0), (0x2000, 0x3000)):
        fixtures.append({'address': 0x82DA3488, 'r3': 0x1000,
            'memory': {0x1050: outer, 0x207C: inner, 0x3000: 0x4000, 0x411C: 0x5000},
            'byte_addresses': []})
    for fixture in fixtures:
        expected = execute_leaf(bytes.fromhex(RANGES[fixture['address']]), fixture['address'],
                                {3: fixture['r3']}, fixture['memory'])
        fixture['expected_return'], fixture['expected_dispatch'] = expected['return'], expected['dispatch'] or 0
    return fixtures


def harness_text(bodies, fixtures):
    text = '#include "mc2_probe_pch.h"\n#include <cstdio>\n#include <cstring>\n'
    text += 'static uint32_t recorded_dispatch = 0;\n#undef REX_CALL_INDIRECT_FUNC\n'
    text += '#define REX_CALL_INDIRECT_FUNC(address) do { recorded_dispatch = (address); } while (0)\n'
    text += '\n'.join(bodies[address]['body'] for address in sorted(bodies))
    text += '\nint main() {\n alignas(32) unsigned char memory[65536]{};\n uint8_t* base = memory;\n PPCContext ctx{};\n'
    for number, fixture in enumerate(fixtures):
        text += 'std::memset(memory, 0, sizeof(memory)); ctx = PPCContext{}; recorded_dispatch = 0;\n'
        text += f'ctx.r3.u32 = {fixture["r3"]}u;\n'
        for address, value in fixture['memory'].items():
            width = 8 if address in fixture['byte_addresses'] else 32
            text += f'REX_STORE_U{width}({address}u, {value}u);\n'
        text += f'sub_{fixture["address"]:08X}(ctx, base);\n'
        text += f'std::printf("CASE {number} %u %u\\n", ctx.r3.u32, recorded_dispatch);\n'
    return text + 'return 0;\n}\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('generated', 'sdk', 'compiler', 'vcvars', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(argv)
    compiler, generated, sdk, output = map(lambda p: p.resolve(),
        (args.compiler, args.generated, args.sdk, args.output))
    if os.name != 'nt' or digest(compiler) != CLANG_CL_SHA256:
        raise ValueError('expected hash-locked Windows Clang')
    bodies, fixtures = extract_bodies(generated), cases()
    if output == generated or generated in output.parents:
        raise ValueError('output must be outside generated tree')
    output.mkdir(parents=True, exist_ok=False)
    source, exe = output/'leaf-harness.cpp', output/'leaf-harness.exe'
    source.write_text(harness_text(bodies, fixtures), encoding='utf-8')
    command = [str(compiler), '/nologo', '/Brepro', '/std:c++latest', '/utf-8', '/O2',
        '/DSPDLOG_FMT_EXTERNAL', '/DSPDLOG_COMPILED_LIB', '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN',
        '/EHa', '/arch:AVX2', '/bigobj', '/MD', '/I'+str(sdk/'include'), '/I'+str(generated),
        str(source), '/Fo'+str(output/'leaf-harness.obj'), '/Fe'+str(exe), '/link', '/Brepro']
    env = vc_environment(args.vcvars.resolve())
    result = {'compiler_sha256': digest(compiler), 'bodies': bodies, 'fixtures': fixtures,
              'compile_command': command, 'harness_sha256': digest(source),
              'dispatch_boundary': 'RECORD ONLY; no guest callee execution', 'game_execution': 'NOT TESTED'}
    with (output/'compile.txt').open('x', encoding='utf-8') as stream:
        process = subprocess.run(command, cwd=output, env=env, stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, timeout=600, check=False)
    result['compile_exit_status'] = process.returncode
    result['success'] = False
    if process.returncode == 0:
        run = subprocess.run([str(exe)], cwd=output, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=30, check=False)
        (output/'run.txt').write_text(run.stdout+run.stderr, encoding='utf-8')
        expected = ''.join(f'CASE {n} {case["expected_return"]} {case["expected_dispatch"]}\n' for n, case in enumerate(fixtures))
        result.update(run_exit_status=run.returncode, literal_output=run.stdout,
                      expected_output=expected, executable_sha256=digest(exe),
                      success=run.returncode == 0 and run.stdout == expected and not run.stderr)
    (output/'leaf-harness.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(f'GENERATED_LEAF_HARNESS cases={len(fixtures)} compile_exit={process.returncode} success={result["success"]}')
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
