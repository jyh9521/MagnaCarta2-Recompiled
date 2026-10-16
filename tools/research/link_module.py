"""Hash-locked full generated-module host link and SDK initialization probe.

All objects are explicit link inputs, /OPT:NOREF and /OPT:NOICF preserve them.
No guest entrypoint is launched and no unresolved symbol is replaced by a stub.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from tools.research.compile_module import digest, inventory, vc_environment
from tools.research.probe_route_a import CLANG_CL_SHA256

LIBRARIES = ('rexruntime.lib', 'spdlog.lib', 'fmt.lib')
SYSTEM_LIBRARIES = ('dxgi.lib', 'dxguid.lib', 'user32.lib')
NATIVE_GENERATED_TREE = '2f665e02be216bc4e87ed8544bd29bf2d0b24dde92857506b492bd18056a43db'


def validate_native_profile(generated_identity):
    if generated_identity.get('tree_sha256') != NATIVE_GENERATED_TREE:
        raise ValueError('native probe requires the verified generated game profile')


def verified_objects(build_dir, generated):
    build_dir, generated = Path(build_dir).resolve(), Path(generated).resolve()
    report = json.loads((build_dir / 'module-build.json').read_text(encoding='utf-8'))
    inputs = json.loads((build_dir / 'inputs.json').read_text(encoding='utf-8'))
    records = report.get('records', [])
    if not report.get('success') or not report.get('inputs_unchanged') or len(records) != 197:
        raise ValueError('expected complete successful 197-object build')
    if inventory(generated) != inputs['generated']:
        raise ValueError('generated tree differs from successful build')
    if len({r['source'] for r in records}) != 197:
        raise ValueError('duplicate generated source records')
    if {r['source'] for r in records} != {p.name for p in generated.glob('*.cpp')}:
        raise ValueError('generated source inventory differs from objects')
    objects = []
    for record in records:
        obj = Path(record['object']).resolve()
        if obj.parent != build_dir / 'objects':
            raise ValueError('object escapes build object directory')
        if not record.get('success') or record.get('exit_status') != 0:
            raise ValueError('unsuccessful object record')
        if obj.stat().st_size != record['object_size'] or digest(obj) != record['object_sha256']:
            raise ValueError('object identity mismatch: ' + obj.name)
        objects.append(obj)
    return objects, inputs


def run_record(argv, output, name, env, timeout=300):
    log = output / (name + '.txt')
    record = {'command': list(map(str, argv)), 'cwd': str(output), 'stdin': 'DEVNULL'}
    started = time.monotonic()
    with log.open('x', encoding='utf-8') as stream:
        try:
            record['exit_status'] = subprocess.run(argv, cwd=output, env=env, stdin=subprocess.DEVNULL,
                stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, check=False).returncode
        except subprocess.TimeoutExpired:
            stream.write('\nHOST_TIMEOUT\n'); record['exit_status'] = 124
        except OSError as exc:
            stream.write(str(exc) + '\n'); record['exit_status'] = 127
    record.update(elapsed_seconds=round(time.monotonic()-started, 3), log=str(log), log_sha256=digest(log))
    (output / (name + '.json')).write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    return record


def link_command(linker, output, objects, host_objects, sdk):
    return [str(linker), '/NOLOGO', '/OUT:' + str(output / 'module_probe.exe'),
            '/OPT:NOREF', '/OPT:NOICF', '/INCREMENTAL:NO', '/Brepro',
            '/MAP:' + str(output / 'host.map'), '/LIBPATH:' + str(sdk / 'lib'),
            *map(str, host_objects), *map(str, objects), *LIBRARIES, *SYSTEM_LIBRARIES]


def runtime_path(env, sdk):
    env = dict(env)
    key = next((k for k in env if k.lower() == 'path'), 'PATH')
    env[key] = str(sdk / 'bin') + os.pathsep + env.get(key, '')
    return env


def title_thread_resumed(run_text):
    """An exact SDK Resume marker, not a claim that title initialization finished."""
    return 'TITLE_RESUMED status=00000000' in run_text.splitlines()


def verified_dependencies(source, dependencies):
    """Explicit local headers are guarded inputs, never implicit ambient source."""
    source=Path(source).resolve(); result=[]
    for candidate in dependencies:
        p=Path(candidate)
        if p.is_symlink() or not p.is_file() or p.suffix.lower() not in ('.h','.hpp'):
            raise ValueError('host dependency must be a regular header')
        p=p.resolve()
        if p.parent!=source.parent or p in result:
            raise ValueError('host dependency must be unique and next to its source')
        result.append(p)
    return result


def build(build_dir, generated, sdk, compiler, linker, source, output, env, probe_source=None,
          *, run_environment=None, expected_markers=None, run_timeout=120, runtime_assets=(), source_dependencies=()):
    build_dir, generated, sdk, compiler, linker, source, output = [Path(p).resolve() for p in
        (build_dir, generated, sdk, compiler, linker, source, output)]
    if digest(compiler) != CLANG_CL_SHA256:
        raise ValueError('Clang compiler SHA-256 mismatch')
    for root in (build_dir, generated, sdk, source.parent):
        if output == root or root in output.parents:
            raise ValueError('output must be outside input trees')
    objects, previous = verified_objects(build_dir, generated)
    if probe_source: validate_native_profile(previous['generated'])
    if inventory(sdk / 'include') != previous['sdk_include']:
        raise ValueError('SDK headers differ from object build')
    sdk_before = inventory(sdk)
    resource = compiler.parent.parent / 'lib/clang/20/include'
    resource_before = inventory(resource) if resource.is_dir() else None
    if previous.get('compiler_resource_headers') != resource_before:
        raise ValueError('Clang resource headers differ from object build')
    source_paths = [source] + ([Path(probe_source).resolve()] if probe_source else [])
    if len(set(source_paths)) != len(source_paths):
        raise ValueError('duplicate host probe source')
    dependencies=verified_dependencies(source,source_dependencies)
    before = {str(p): digest(p) for p in [compiler, linker, *source_paths, *dependencies, *objects]}
    output.mkdir(parents=True, exist_ok=False)
    copied_assets = []
    for asset in runtime_assets:
        asset = Path(asset).resolve()
        if asset.parent != sdk / 'bin' or asset.suffix.lower() != '.dll':
            raise ValueError('runtime asset must be an SDK bin DLL')
        destination = output / asset.name
        if destination.exists(): raise ValueError('duplicate runtime asset')
        shutil.copyfile(asset, destination)
        if digest(asset) != digest(destination): raise ValueError('runtime asset copy mismatch')
        copied_assets.append({'source':str(asset),'path':str(destination),'sha256':digest(asset)})
    identities = {'schema': 1, 'input_hashes': before, 'sdk': sdk_before,
                  'generated': previous['generated'], 'explicit_object_count': len(objects),
                  'libraries': {name: digest(sdk / 'lib' / name) for name in LIBRARIES},
                  'environment': {k:v for k,v in env.items() if k.upper() in ('LIB','INCLUDE','VCTOOLSVERSION','WINDOWSSDKVERSION')}}
    identities['compiler_resource_headers']=resource_before
    identities['runtime_assets']=copied_assets
    identities['host_source_snapshots']=[]
    for i, path in enumerate(source_paths):
        snapshot=output/f'source-{i}.cpp';snapshot.write_bytes(path.read_bytes())
        identities['host_source_snapshots'].append({'path':str(snapshot),'sha256':digest(snapshot),'original':str(path)})
    identities['host_header_snapshots']=[]
    for i,path in enumerate(dependencies):
        snapshot=output/f'header-{i}.h';snapshot.write_bytes(path.read_bytes())
        identities['host_header_snapshots'].append({'path':str(snapshot),'sha256':digest(snapshot),'original':str(path)})
    (output / 'inputs.json').write_text(json.dumps(identities, indent=2)+'\n', encoding='utf-8')
    records, host_objects = [], []
    for i, item in enumerate(source_paths):
        obj = output / f'host-{i}.obj'; host_objects.append(obj)
        argv = [str(compiler), '/nologo', '/c', '/Brepro', '/std:c++latest', '/MD', '/EHa', '/arch:AVX2',
                '/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN',
                '/I'+str(sdk/'include'), '/I'+str(generated), str(item), '/Fo'+str(obj)]
        if probe_source: argv.append('/DMC2_NATIVE_PROBE')
        record = run_record(argv, output, 'compile-' + str(i), env); records.append(record)
        if record['exit_status'] or not obj.is_file(): break
    if len(records) == len(source_paths) and all(r['exit_status'] == 0 for r in records) and all(p.is_file() for p in host_objects):
        records.append(run_record(link_command(linker,output,objects,host_objects,sdk),output,'link',env))
        if records[-1]['exit_status'] == 0 and (output/'module_probe.exe').is_file():
            execution_environment = dict(env)
            if run_environment:
                execution_environment.update(run_environment)
            records.append(run_record([str(output/'module_probe.exe')],output,'run',runtime_path(execution_environment,sdk),run_timeout))
    stable = before == {p:digest(p) for p in before} and sdk_before == inventory(sdk) and previous['generated'] == inventory(generated)
    if resource_before is not None: stable = stable and resource_before == inventory(resource)
    run_text = (output/'run.txt').read_text(encoding='utf-8') if (output/'run.txt').is_file() else ''
    expected = len(re.findall(r'^\s*registrar->SetFunction\(', (generated/'mc2_probe_register.cpp').read_text(encoding='utf-8'),re.M))
    markers = ['SETUP status=00000000', f'REGISTRATION count={expected} base=mapped', 'MEMORY roundtrip=12345678', 'SHUTDOWN complete']
    if probe_source: markers.append('NATIVE_PROBE status=0')
    if expected_markers is not None: markers = list(expected_markers)
    runtime_line = [line[12:] for line in run_text.splitlines() if line.startswith('RUNTIME_DLL ')]
    runtime_verified = len(runtime_line)==1 and Path(runtime_line[0]).resolve()==(sdk/'bin/rexruntime.dll').resolve()
    marker_verified = all(m in run_text.splitlines() for m in markers)
    complete = len(records) == len(source_paths)+2 and all(r['exit_status']==0 for r in records)
    result = {'schema':1,'object_count':len(objects),'expected_mappings':expected,'records':records,
              'inputs_unchanged':stable,'runtime_markers_verified':marker_verified,'runtime_dll_verified':runtime_verified,
              'guest_entrypoint_launched': title_thread_resumed(run_text),
              'title_thread_resumed': title_thread_resumed(run_text),
              'game_boot': 'ENTRY THREAD RESUMED; execution requires diagnostic stack proof' if title_thread_resumed(run_text) else 'NOT TESTED',
              'success':complete and stable and marker_verified and runtime_verified}
    if probe_source: result['native_profile_generated_tree']=NATIVE_GENERATED_TREE
    result['runtime_environment_overrides'] = dict(run_environment or {})
    result['expected_runtime_markers'] = markers
    result['run_timeout_seconds'] = run_timeout
    result['runtime_assets'] = copied_assets
    result['runtime_assets_unchanged'] = all(digest(item['path']) == item['sha256'] for item in copied_assets)
    result['success'] = result['success'] and result['runtime_assets_unchanged']
    if probe_source: result['probe_source']={'path':str(source_paths[1]),'sha256':before[str(source_paths[1])]}
    for name in ('module_probe.exe','host.map'):
        p=output/name
        if p.is_file(): result[name]={'sha256':digest(p),'size':p.stat().st_size}
    (output/'host-link.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(f"HOST_LINK objects={len(objects)} mappings={expected} inputs_unchanged={stable} success={result['success']}",flush=True)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build-dir','generated','sdk','compiler','vcvars','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--source',type=Path,default=Path('src/host/module_probe.cpp'))
    parser.add_argument('--probe-source',type=Path)
    args=parser.parse_args(argv)
    try:
        if os.name!='nt': raise ValueError('real host link requires Windows VS x64 environment')
        env=vc_environment(args.vcvars.resolve())
        linker=Path(env['VCToolsInstallDir'])/'bin/Hostx64/x64/link.exe'
        result=build(args.build_dir,args.generated,args.sdk,args.compiler,linker,args.source,args.output,env,args.probe_source)
        return 0 if result['success'] else 1
    except (OSError,ValueError,KeyError) as exc:
        print('HOST_LINK_ERROR: '+str(exc),file=sys.stderr);return 1


if __name__=='__main__': raise SystemExit(main())
