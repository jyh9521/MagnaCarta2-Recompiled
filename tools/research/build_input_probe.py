"""Build the independent bounded input diagnostic, never game code or SDK code."""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path
from tools.research.compile_module import digest, vc_environment, inventory
from tools.research.link_module import run_record
from tools.research.probe_route_a import CLANG_CL_SHA256

SDK_SHA256 = 'e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('sdk', 'compiler', 'vcvars', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args()
    sdk, compiler, output = args.sdk.resolve(), args.compiler.resolve(), args.output.resolve()
    if digest(sdk / 'bin/rexruntime.dll') != SDK_SHA256:
        p.error('unsupported SDK identity')
    if digest(compiler) != CLANG_CL_SHA256:
        p.error('unsupported compiler identity')
    if output == sdk or sdk in output.parents:
        p.error('output must be outside SDK')
    if output.exists():
        p.error('output must be a new directory')
    root = Path(__file__).resolve().parents[2]
    sources = [root / 'src/host' / name for name in ('input_refresh_probe.cpp',
               'input_probe_capture.cpp', 'input_probe_trace.h', 'input_call_gate.h')]
    env = vc_environment(args.vcvars.resolve())
    linker = shutil.which('link.exe', path=next(v for k, v in env.items() if k.lower() == 'path'))
    if not linker:
        p.error('MSVC linker absent')
    sdk_before = inventory(sdk)
    output.mkdir(parents=True)
    inputs = {str(path): digest(path) for path in [*sources, compiler, Path(linker), sdk / 'lib/rexruntime.lib', sdk / 'bin/rexruntime.dll']}
    snapshots = output / 'sources'; snapshots.mkdir()
    for path in sources:
        (snapshots / path.name).write_bytes(path.read_bytes())
    records = []
    for source, name, libraries in [(sources[0], 'probe', [str(sdk / 'lib/rexruntime.lib'), 'kernel32.lib']),
                                    (sources[1], 'capture', ['kernel32.lib', 'dbghelp.lib'])]:
        command = [str(compiler), '/nologo', '/c', '/std:c++latest', '/MD', '/EHsc', '/Zi',
                   '/DNOMINMAX', '/DWIN32_LEAN_AND_MEAN', '/DSPDLOG_FMT_EXTERNAL', '/DSPDLOG_COMPILED_LIB',
                   '/I' + str(sdk / 'include'), '/I' + str(snapshots), str(snapshots / source.name),
                   '/Fo' + str(output / (name + '.obj')), '/Fd' + str(output / (name + '.pdb'))]
        record = run_record(command, output, name + '-compile', env, 120); records.append(record)
        if record['exit_status']:
            raise SystemExit(record['exit_status'])
        command = [linker, '/nologo', '/OUT:' + str(output / (name + '.exe')),
                   str(output / (name + '.obj')), *libraries, '/INCREMENTAL:NO', '/DEBUG',
                   '/PDB:' + str(output / (name + '-link.pdb'))]
        record = run_record(command, output, name + '-link', env, 120); records.append(record)
        if record['exit_status']:
            raise SystemExit(record['exit_status'])
    if inventory(sdk) != sdk_before:
        raise ValueError('SDK input changed during build')
    with (output / 'identity.json').open('x', encoding='utf-8') as stream:
        json.dump(dict(inputs=inputs, sdk=sdk_before, outputs={name: digest(output / name) for name in ('probe.exe', 'capture.exe')},
                       records=records), stream, indent=2)
    print('INPUT_PROBE_BUILD compile=0 link=0 game_loaded=0 SDK_modified=0')


if __name__ == '__main__':
    main()
