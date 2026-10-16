"""Link all verified objects and record an isolated, real SDK title-entry attempt.

A diagnostic result is not a successful game boot. Missing data and missing
subsystems remain explicit environmental blockers; this tool never bypasses them.
"""
from __future__ import annotations
import argparse
import bisect
import json
import os
from pathlib import Path
import re
import sys

from tools.research import link_module
from tools.research.compile_module import digest, inventory, vc_environment

XEX_SHA256 = '26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f'


def validate_image(path, game_root):
    path, game_root = Path(path).resolve(), Path(game_root).resolve()
    if not path.is_file() or digest(path) != XEX_SHA256:
        raise ValueError('title probe requires the verified disc-1 XEX')
    mounted = game_root / path.name
    if not mounted.is_file() or digest(mounted) != XEX_SHA256:
        raise ValueError('game root must contain the same verified XEX basename')
    return {'source': str(path), 'mounted': str(mounted), 'sha256': XEX_SHA256}


def map_symbols(text):
    base = re.search(r'Preferred load address is\s+([0-9a-fA-F]+)', text)
    if not base:
        raise ValueError('linker map missing preferred load address')
    base = int(base[1], 16)
    symbols = []
    for name, value in re.findall(r'^\s*[0-9A-Fa-f]{4}:[0-9A-Fa-f]+\s+(\S+)\s+([0-9A-Fa-f]{16})\s+f\b', text, re.M):
        if not name.startswith('__imp__'):
            symbols.append((int(value,16)-base, name))
    if not symbols:
        raise ValueError('linker map has no function symbols')
    return sorted(symbols)


def resolve_rva(symbols, rva):
    index = bisect.bisect_right([value for value, _ in symbols], rva)-1
    if index < 0:
        return None
    address, name = symbols[index]
    return {'name':name,'rva':address,'offset':rva-address,
            'interpretation':'nearest preceding linker function symbol; not source-line proof'}


def diagnostic_input_guards(result, report):
    """Runtime failure is expected; each independent identity guard still applies."""
    return bool(result['inputs_unchanged'] and result['runtime_dll_verified'] and
                result.get('runtime_assets_unchanged', True) and
                report['game_input_unchanged'] and report['gpu_plugin_path_verified'])


def analyze(run_text, sdk_text, symbols, exit_status):
    """Only positive observed markers establish progression; timeouts are not a location."""
    lines = run_text.splitlines()
    loaded = 'TITLE_LOAD status=00000000' in lines
    resumed = 'TITLE_RESUMED status=00000000' in lines
    fault = re.search(r'^TITLE_EXCEPTION code=([0-9A-F]{8}) ip=([0-9A-Fa-f]+) phase=(\d+) thread=(\d+)$',run_text,re.M)
    frames=[]
    for number, address, rva, module in re.findall(r'^TITLE_STACK (\d+) address=([0-9A-Fa-f]+) rva=([0-9A-Fa-f]+) module=(.+)$',run_text,re.M):
        item={'index':int(number),'address':int(address,16),'rva':int(rva,16),'module':module}
        if Path(module.replace('\\','/')).name.lower()=='module_probe.exe':
            item['nearest_symbol']=resolve_rva(symbols,item['rva'])
        frames.append(item)
    memory=re.search(r'^TITLE_FAULT operation=(\d+) address=([0-9A-Fa-f]+) guest_offset=([0-9A-Fa-f]+)$',run_text,re.M)
    missing = re.findall(r"\[NtCreateFile\] FAILED: path='([^']+)' -> (0x[0-9a-fA-F]+)",sdk_text)
    names=[f['nearest_symbol']['name'] for f in frames if f.get('nearest_symbol')]
    native = re.search(r'^TITLE_NATIVES guard=(\d+) bound=(\d+) fallback=(\d+) int_const=([0-9A-F]+) add=([0-9A-F]+)$',run_text,re.M)
    samples=[]
    for number, pc, registers in re.findall(r'^TITLE_SAMPLE sample=(\d+) pc=([0-9A-Fa-f]+) (.+)$',run_text,re.M):
        samples.append({'sample':int(number),'pc':int(pc,16),'registers':dict((name,int(value,16)) for name,value in re.findall(r'(r\d+|lr|ctr)=([0-9A-Fa-f]+)',registers))})
    sample_frames=[]
    for sample, index, address, rva, module in re.findall(r'^TITLE_SAMPLE_STACK sample=(\d+) index=(\d+) address=([0-9A-Fa-f]+) rva=([0-9A-Fa-f]+) module=(.+)$',run_text,re.M):
        item={'sample':int(sample),'index':int(index),'address':int(address,16),'rva':int(rva,16),'module':module}
        if Path(module.replace('\\','/')).name.lower()=='module_probe.exe':item['nearest_symbol']=resolve_rva(symbols,item['rva'])
        sample_frames.append(item)
    result={'schema':1,'image_loaded':loaded,'guest_entrypoint_launched':resumed,
            'exit_status':exit_status,'timed_out':exit_status==124,'stack':frames,
            'main_candidate_observed':'sub_82E1F578' in names,
            'original_entry_execution_observed':loaded and resumed and 'xstart' in names,
            'failed_file_operations':[{'path':p,'status':s} for p,s in missing],
            'game_boot_success':False,'diagnostic_success':bool(loaded and resumed and fault and frames and exit_status not in (0,124,127)),
            'shutdown_verified':False,
            'scope':'real initialization attempt; no assertion bypass, guest patch, or recovery from fault'}
    result.update(samples=samples,sample_stack=sample_frames,
                  sampling_scope='brief native-thread scheduling suspension only; no registers or guest bytes changed')
    rings=[]
    for sample, values in re.findall(r'^TITLE_RING sample=(\d+) (.+)$',run_text,re.M):
        rings.append({'sample':int(sample),**{name:int(value,16) for name,value in re.findall(r'(\w+)=([0-9A-Fa-f]+)',values)}})
    result['ring_samples']=rings
    sampled_names=[f['nearest_symbol']['name'] for f in sample_frames if f.get('nearest_symbol')]
    result['original_entry_execution_observed'] |= loaded and resumed and 'xstart' in sampled_names
    result['main_candidate_observed'] |= 'sub_82E1F578' in sampled_names
    result['stack_sample_observed']=loaded and resumed and len(samples)==3 and bool(sample_frames)
    result['observation_window_elapsed']='TITLE_WAIT result=2 running=1' in lines
    fatal=re.search(r'^TITLE_FATAL .*Call to invalid or unregistered function at guest address 0x([0-9a-fA-F]+)$',run_text,re.M)
    fatal_frames=[]
    for sample,index,address,rva,module in re.findall(r'^TITLE_FATAL_STACK sample=(\d+) index=(\d+) address=([0-9A-Fa-f]+) rva=([0-9A-Fa-f]+) module=(.+)$',run_text,re.M):
        item={'index':int(index),'address':int(address,16),'rva':int(rva,16),'module':module}
        if Path(module.replace('\\','/')).name.lower()=='module_probe.exe':item['nearest_symbol']=resolve_rva(symbols,item['rva'])
        fatal_frames.append(item)
    if fatal:
        result['unregistered_guest_target']=int(fatal[1],16)
        result['fatal_stack']=fatal_frames
        expected_fatal=f'Call to invalid or unregistered function at guest address 0x{int(fatal[1],16):08X}'
        result['sdk_fatal_corroborated']=expected_fatal.lower() in sdk_text.lower()
        result['diagnostic_success']=loaded and resumed and bool(fatal_frames) and exit_status not in (0,124,127) and result['sdk_fatal_corroborated']
        fatal_names=[f['nearest_symbol']['name'] for f in fatal_frames if f.get('nearest_symbol')]
        result['original_entry_execution_observed'] |= loaded and resumed and 'xstart' in fatal_names
        result['main_candidate_observed'] |= 'sub_82E1F578' in fatal_names
    if fault:result['exception']={'code':fault[1],'instruction_pointer':int(fault[2],16),'phase':int(fault[3]),'thread':int(fault[4])}
    if memory:
        offset=int(memory[3],16)
        result['fault_memory']={'operation':int(memory[1]),'host_address':int(memory[2],16),
                                'guest_offset':offset if offset<=0xFFFFFFFF else None}
    if native:result['natives']={'guard':int(native[1]),'bound':int(native[2]),'fallback':int(native[3]),
                                'int_const':int(native[4],16),'add':int(native[5],16)}
    if fatal:result['blocker_classification']='compatibility: SDK function dispatch rejected a guest target; no bypass applied'
    elif missing:result['blocker_classification']='environment: failed file operations precede fault; investigate optional-vs-required data before attribution'
    elif fault:result['blocker_classification']='fault captured; investigate stack and subsystem configuration before classifying defect'
    else:result['blocker_classification']='no positively located blocker'
    return result


CALLBACK_GENERATED_TREE = '1328d2c4799d39cafe2f14787ea9625a84b9ef874fc63cd494f7543f217790fc'
VIRTUAL_THUNK_GENERATED_TREE = 'f79198eb4739d0939cf10f7aece3d11d06d56950076696428a7845a84a4fca74'
COMPARE_GENERATED_TREE = '14c27505807e3381f5d9f4b20ab84a1b6f3404ea95204c134d5957260fbc2148'
NATIVE_GATEWAY_GENERATED_TREE = '994d2db123de56faf27f0560d872bb2481e6fa9f9c9e8123e6fe44d8a76f171b'


def validate_title_profile(identity):
    """Only independently audited original-game discovery profiles."""
    if identity.get('tree_sha256') == NATIVE_GATEWAY_GENERATED_TREE:
        return 'native-gateway-82509380'
    if identity.get('tree_sha256') == COMPARE_GENERATED_TREE:
        return 'compare-callback-82C1C1A0'
    if identity.get('tree_sha256') == VIRTUAL_THUNK_GENERATED_TREE:
        return 'virtual-thunk-823C2740'
    if identity.get('tree_sha256') == CALLBACK_GENERATED_TREE:
        return 'callback-entry-8234FF10'
    link_module.validate_native_profile(identity)
    return 'phase5-missing-callback-baseline'


def execute(args):
    previous=json.loads((args.build_dir/'inputs.json').read_text(encoding='utf-8'))
    profile = validate_title_profile(previous['generated'])
    image=validate_image(args.xex,args.game_root or args.xex.parent)
    root=(args.game_root or args.xex.parent).resolve()
    if args.output.resolve()==root or root in args.output.resolve().parents:
        raise ValueError('diagnostic output must be outside the game input tree')
    root_before=inventory(root)
    env=vc_environment(args.vcvars.resolve())
    linker=Path(env['VCToolsInstallDir'])/'bin/Hostx64/x64/link.exe'
    overrides={'MC2_XEX_PATH':image['source'],'MC2_GAME_ROOT':str((args.game_root or args.xex.parent).resolve())}
    assets=[]
    if args.gpu:
        overrides['MC2_GPU_PLUGIN']='xenos';assets=[args.sdk/'bin/rexgpu-xenos.dll']
    else:overrides['MC2_GPU_PLUGIN']=''
    result=link_module.build(args.build_dir,args.generated,args.sdk,args.compiler,linker,args.source,args.output,env,
        run_environment=overrides,expected_markers=['SETUP status=00000000','TITLE_LOAD status=00000000','TITLE_RESUMED status=00000000'],
        run_timeout=35,runtime_assets=assets)
    output=args.output.resolve()
    run_text=(output/'run.txt').read_text(encoding='utf-8',errors='replace') if (output/'run.txt').exists() else ''
    sdk_text=(output/'title-sdk.log').read_text(encoding='utf-8',errors='replace') if (output/'title-sdk.log').exists() else ''
    map_path=output/'host.map'
    symbols=map_symbols(map_path.read_text(encoding='utf-8')) if map_path.exists() else []
    run=next((r for r in result['records'] if Path(r['log']).name=='run.txt'),{})
    report=analyze(run_text,sdk_text,symbols,run.get('exit_status',127))
    report.update(image=image,generated_profile=profile,inputs_unchanged=result['inputs_unchanged'],object_count=result['object_count'],
                  host_build_success=result['success'],gpu_requested=args.gpu)
    report['game_input_before']=root_before
    report['game_input_after']=inventory(root)
    report['game_input_unchanged']=report['game_input_before']==report['game_input_after'] and digest(args.xex)==XEX_SHA256
    gpu_paths=re.findall(r'^TITLE_GPU plugin_loaded backend=any presentation=false path=(.+)$',run_text,re.M)
    report['gpu_plugin_path_verified']=not args.gpu or (len(gpu_paths)==1 and Path(gpu_paths[0]).resolve()==output/'rexgpu-xenos.dll')
    for name in ('run.txt','title-sdk.log','host.map','title-natives.bin'):
        p=output/name
        if p.is_file():report[name]={'path':str(p),'sha256':digest(p),'size':p.stat().st_size}
    report['runtime_assets_unchanged']=result.get('runtime_assets_unchanged',True)
    report['diagnostic_success'] &= diagnostic_input_guards(result,report)
    (output/'title-entry.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f"TITLE_ENTRY resumed={report['guest_entrypoint_launched']} located={report['diagnostic_success']} game_boot=False",flush=True)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build-dir','generated','sdk','compiler','vcvars','xex','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--game-root',type=Path)
    parser.add_argument('--source',type=Path,default=Path('src/host/title_probe.cpp'))
    parser.add_argument('--gpu',action='store_true',help='request the unmodified SDK xenos plugin, no presentation')
    args=parser.parse_args(argv)
    try:
        if os.name!='nt':raise ValueError('title entry requires Windows SDK host')
        return 0 if execute(args)['diagnostic_success'] else 1
    except (OSError,ValueError,KeyError) as error:
        print('TITLE_ENTRY_ERROR: '+str(error),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
