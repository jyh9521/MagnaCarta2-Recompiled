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
from tools.research.event_trace_report import parse_event_trace
from tools.research.schedule_trace_report import parse_schedule_trace
from tools.research.counter_trace_report import parse_counter_trace
from tools.research.queue_watch_report import read_queue_watches
from tools.research.panic_capture_report import parse_panic_capture
from tools.research.critical_section_capture_report import parse_critical_section_capture
from tools.research.compile_module import digest, inventory, vc_environment

GPU_PLUGIN_SHA256 = '0c23cfa23fc4fa5638dc8a3dc0de87b1041d97705d4677774083f1f350cd8d89'
WAIT_SDK_SHA256 = 'e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a'
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


def make_symbol_resolver(symbols):
    """Index once for bulk native traces; never rebuild 58k addresses per PC."""
    addresses=tuple(value for value,_ in symbols)
    def lookup(rva):
        index=bisect.bisect_right(addresses,rva)-1
        if index<0:return None
        address,name=symbols[index]
        return {'name':name,'rva':address,'offset':rva-address,
                'interpretation':'nearest preceding linker function symbol; not source-line proof'}
    return lookup


def diagnostic_input_guards(result, report):
    """Runtime failure is expected; each independent identity guard still applies."""
    return bool(result['inputs_unchanged'] and result['runtime_dll_verified'] and
                result.get('runtime_assets_unchanged', True) and
                report['game_input_unchanged'] and report['gpu_plugin_path_verified'])


def presentation_observation(run_text):
    lines=run_text.splitlines()
    required=('PRESENTATION_CONTEXT initialized=1 ui_thread=1',
              'PRESENTATION_SETUP status=00000000 has_presentation=1 presenter=1',
              'PRESENTATION_WINDOW open=1 hidden=1 binding_requested=1',
              'TITLE_PRESENTATION bound_before_setup=1 hidden=1')
    positions=[lines.index(line) for line in required if line in lines]
    initialized=len(positions)==len(required) and positions==sorted(positions) and all(lines.count(line)==1 for line in required)
    return {'initialized':initialized,
            'loop_entered':'PRESENTATION_LOOP enter=1' in lines,
            'loop_exited':'PRESENTATION_LOOP exit=0' in lines,
            'surface_verified':False,'visible_frame_verified':False,'title_shutdown_verified':False}


def wait_observations(run_text):
    result=[]
    for values in re.findall(r'^TITLE_WAIT_OBJECT (.+)$',run_text,re.M):
        fields=dict(re.findall(r'(\w+)=([^ ]+)',values))
        if not {'sample','handle','status','scope'}<=fields.keys():continue
        if fields['scope']!='public-readonly':continue
        result.append(fields)
    return result


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
    result['sdk_guest_faults']=[{'operation':op,'guest_address':int(address,16)} for op,address in re.findall(r'Unhandled guest access violation: (\w+) of guest 0x([0-9A-Fa-f]+)',sdk_text)]
    result['presentation']=presentation_observation(run_text)
    result['wait_objects']=wait_observations(run_text)
    result['bounded_observation'] = bool(result['observation_window_elapsed'] and result['stack_sample_observed'] and exit_status == 26 and not fault and not fatal and not result['sdk_guest_faults'])
    result['presenter_null_reports'] = sdk_text.count('IssueSwap: presenter is null')
    if fatal:result['blocker_classification']='compatibility: SDK function dispatch rejected a guest target; no bypass applied'
    elif result['bounded_observation']:result['blocker_classification']='bounded observation: title thread still running at the observation limit; sampled wait is not proof of deadlock or game boot'
    elif missing and (fault or result['sdk_guest_faults']):result['blocker_classification']='environment: failed file operations precede fault; investigate optional-vs-required data before attribution'
    elif fault or result['sdk_guest_faults']:result['blocker_classification']='fault captured; investigate stack and subsystem configuration before classifying defect'
    else:result['blocker_classification']='no positively located blocker'
    return result


CALLBACK_GENERATED_TREE = '1328d2c4799d39cafe2f14787ea9625a84b9ef874fc63cd494f7543f217790fc'
VIRTUAL_THUNK_GENERATED_TREE = 'f79198eb4739d0939cf10f7aece3d11d06d56950076696428a7845a84a4fca74'
COMPARE_GENERATED_TREE = '14c27505807e3381f5d9f4b20ab84a1b6f3404ea95204c134d5957260fbc2148'
BYTE_FLAG_GENERATED_TREE = '9f5eda2bd7aa3934a32187063b2365864f502927ed67984f3cc02fa740d8fee6'
WORD_LEAF_GENERATED_TREE = '628b54be3f51aa9f6ac198818102330a2e896a81765055f55a592c4144177f60'
INDEXED_TAIL_GENERATED_TREE = 'd8336966f006a40c572f70585fbf4c3880554eca6669385d24605fde5a86ffd4'
CONDITIONAL_TAIL_GENERATED_TREE = '641f44328a77585a8d263988f24d6044dfb39f14cd9b2d57f0522fb717c4699f'
BITFIELD_LEAF_GENERATED_TREE = '0144be8ebcfe91c81da80a8a370cb61d096b3cd2ee518117234ccc24cceb2256'
FLOAT_LEAF_GENERATED_TREE = 'cddd7af7516965eb293c850fb07b20e5b6976f759addf906b52ea441e8869767'
EVENT_TRACE_REBUILD_TREE = 'ae88b3e9c6506fa6ca9ac42981653c7736975cbc889a1bbced35a5bd74b034b4'
PRESENTATION_REBUILD_TREE = '8eff0b28ea7e74aada90e1e5f7802a34ed3b9ef7d30867c51bf64231bd573c32'
EXTENDED_NATIVE_GENERATED_TREE = 'bfb05b9fd7122d019d61d691c1764062107928d8262cc84dc4c3a4c8114e0121'
NATIVE_GATEWAY_GENERATED_TREE = '994d2db123de56faf27f0560d872bb2481e6fa9f9c9e8123e6fe44d8a76f171b'


def validate_title_profile(identity):
    """Only independently audited original-game discovery profiles."""
    if identity.get('tree_sha256') == BYTE_FLAG_GENERATED_TREE:
        return 'byte-flag-leaf-82E078C0'
    if identity.get('tree_sha256') == WORD_LEAF_GENERATED_TREE:
        return 'word-leaf-82B7CCD0'
    if identity.get('tree_sha256') == INDEXED_TAIL_GENERATED_TREE:
        return 'indexed-tail-82A3DEA0'
    if identity.get('tree_sha256') == CONDITIONAL_TAIL_GENERATED_TREE:
        return 'conditional-tail-826A9EC8'
    if identity.get('tree_sha256') == BITFIELD_LEAF_GENERATED_TREE:
        return 'bitfield-leaf-82AC2810'
    if identity.get('tree_sha256') == FLOAT_LEAF_GENERATED_TREE:
        return 'float-leaf-82AC1DE8'
    if identity.get('tree_sha256') == EVENT_TRACE_REBUILD_TREE:
        return 'extended-native-event-trace-rebuild'
    if identity.get('tree_sha256') == PRESENTATION_REBUILD_TREE:
        return 'extended-native-presentation-rebuild'
    if identity.get('tree_sha256') == EXTENDED_NATIVE_GENERATED_TREE:
        return 'extended-native-82517D70'
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


def validate_capture_profile(profile, panic=False, critical=False):
    if (panic or critical) and profile not in ('word-leaf-82B7CCD0','byte-flag-leaf-82E078C0'):
        raise ValueError('capture requires an independently verified original caller discovery profile')


def validate_fp_contract(profile, inputs, records):
    """Profiles containing the restored float leaf require strict FP; old rollback profiles stay valid."""
    if profile not in ('float-leaf-82AC1DE8','bitfield-leaf-82AC2810','conditional-tail-826A9EC8','indexed-tail-82A3DEA0','word-leaf-82B7CCD0','byte-flag-leaf-82E078C0'):return
    if inputs.get('floating_point_contract') != 'strict' or not records:
        raise ValueError('discovery profile requires a strict FP module build')
    for row in records:
        flags=[str(x).lower() for x in row.get('command',[])]
        if '/fp:strict' not in flags or any(x.startswith('/fp:') and x!='/fp:strict' for x in flags):
            raise ValueError('discovery object lacks exact strict FP contract')


def execute(args):
    seconds=getattr(args,'observe_seconds',20)
    if not 20<=seconds<=60:raise ValueError('observation must be 20..60 seconds')
    trace=getattr(args,'trace_events',False)
    schedule=getattr(args,'trace_schedule',False)
    counter=getattr(args,'trace_counter',False)
    capture_panic=getattr(args,'capture_panic',False)
    capture_critical=getattr(args,'capture_critical_section',False)
    present=getattr(args,'present',False)
    if present and not args.gpu:raise ValueError('presentation requires the real GPU plugin')
    sdk_runtime=args.sdk/'bin/rexruntime.dll'
    if digest(sdk_runtime)!=WAIT_SDK_SHA256:raise ValueError('wait observation requires the verified SDK runtime DLL')
    if args.gpu and digest(args.sdk/'bin/rexgpu-xenos.dll')!=GPU_PLUGIN_SHA256:
        raise ValueError('unsupported GPU plugin identity')
    previous=json.loads((args.build_dir/'inputs.json').read_text(encoding='utf-8'))
    profile = validate_title_profile(previous['generated'])
    validate_capture_profile(profile,capture_panic or schedule or counter,capture_critical)
    validate_fp_contract(profile,previous,json.loads((args.build_dir/'module-build.json').read_text(encoding='utf-8'))['records'])
    image=validate_image(args.xex,args.game_root or args.xex.parent)
    root=(args.game_root or args.xex.parent).resolve()
    if args.output.resolve()==root or root in args.output.resolve().parents:
        raise ValueError('diagnostic output must be outside the game input tree')
    root_before=inventory(root)
    env=vc_environment(args.vcvars.resolve())
    linker=Path(env['VCToolsInstallDir'])/'bin/Hostx64/x64/link.exe'
    overrides={'MC2_XEX_PATH':image['source'],'MC2_GAME_ROOT':str((args.game_root or args.xex.parent).resolve())}
    overrides['MC2_OBSERVE_SECONDS']=str(seconds)
    overrides['MC2_EVENT_TRACE']='1' if trace else '0'
    overrides['MC2_SCHEDULE_TRACE']='1' if schedule else '0'
    overrides['MC2_COUNTER_TRACE']='1' if counter else '0'
    overrides['MC2_CAPTURE_PANIC']='1' if capture_panic else '0'
    overrides['MC2_CAPTURE_CRITICAL_SECTION']='1' if capture_critical else '0'
    overrides['MC2_PRESENTATION']='1' if present else '0'
    overrides['MC2_WAIT_SDK_SHA256']=WAIT_SDK_SHA256
    dependencies=[args.source.parent/name for name in ('presentation_probe.h','wait_observation.h','event_import_trace.h')]
    has_panic_header='#include "panic_observation.h"' in args.source.read_text(encoding='utf-8-sig')
    if capture_panic and not has_panic_header:raise ValueError('capture requires the read-only observation host header')
    if capture_critical and 'void ObserveCriticalSectionFault(' not in args.source.read_text(encoding='utf-8-sig'):raise ValueError('critical capture requires the read-only observer host source')
    if has_panic_header:dependencies.append(args.source.parent/'panic_observation.h')
    has_schedule_header='#include "schedule_observation.h"' in args.source.read_text(encoding='utf-8-sig')
    if schedule and not has_schedule_header:raise ValueError('schedule trace requires original-caller-gated observation header')
    if has_schedule_header:dependencies.extend(args.source.parent/name for name in ('schedule_import_trace.h','schedule_observation.h'))
    has_counter_header='#include "counter_observation.h"' in args.source.read_text(encoding='utf-8-sig')
    if counter and not has_counter_header:raise ValueError('counter trace requires original-body-gated RAW observation host')
    if has_counter_header:dependencies.extend(args.source.parent/name for name in ('counter_lifecycle_trace.h','counter_observation.h','counter_queue_watch.h','counter_worker_sample.h'))
    assets=[]
    if args.gpu:
        overrides['MC2_GPU_PLUGIN']='xenos';assets=[args.sdk/'bin/rexgpu-xenos.dll']
    else:overrides['MC2_GPU_PLUGIN']=''
    result=link_module.build(args.build_dir,args.generated,args.sdk,args.compiler,linker,args.source,args.output,env,
        run_environment=overrides,expected_markers=['SETUP status=00000000','TITLE_LOAD status=00000000','TITLE_RESUMED status=00000000'],
        run_timeout=seconds+25,runtime_assets=assets,source_dependencies=dependencies)
    output=args.output.resolve()
    run_text=(output/'run.txt').read_text(encoding='utf-8',errors='replace') if (output/'run.txt').exists() else ''
    sdk_text=(output/'title-sdk.log').read_text(encoding='utf-8',errors='replace') if (output/'title-sdk.log').exists() else ''
    map_path=output/'host.map'
    linked=any(Path(r['log']).name=='link.txt' and r['exit_status']==0 for r in result['records'])
    symbols=map_symbols(map_path.read_text(encoding='utf-8')) if linked and map_path.exists() else []
    run=next((r for r in result['records'] if Path(r['log']).name=='run.txt'),{})
    report=analyze(run_text,sdk_text,symbols,run.get('exit_status',127))
    report.update(image=image,generated_profile=profile,inputs_unchanged=result['inputs_unchanged'],object_count=result['object_count'],
                  host_build_success=result['success'],gpu_requested=args.gpu,presentation_requested=present,event_trace_requested=trace)
    report['observation_seconds']=seconds
    report['event_traces']=[]
    trace_resolver=make_symbol_resolver(symbols)
    for reason,name,success in re.findall(r'^EVENT_TRACE_FILE reason=(\w+) path=(event-trace-\d+\.txt) success=([01])$',run_text,re.M):
        path=output/name
        if success!='1' or not path.is_file():continue
        parsed=parse_event_trace(run_text+'\n'+path.read_text(encoding='utf-8',errors='replace'),trace_resolver)
        parsed.update(reason=reason,path=str(path),sha256=digest(path))
        report['event_traces'].append(parsed)
    report['event_trace']=report['event_traces'][-1] if report['event_traces'] else parse_event_trace(run_text)
    report['schedule_trace_requested']=schedule
    report['schedule_traces']=[]
    for reason,name,success in re.findall(r'^SCHEDULE_TRACE_FILE reason=(\w+) path=(schedule-trace-\d+\.txt) success=([01])$',run_text,re.M):
        path=output/name
        if success!='1' or not path.is_file():continue
        parsed=parse_schedule_trace(run_text+'\n'+path.read_text(encoding='utf-8',errors='replace'),requested=schedule)
        parsed.update(reason=reason,path=str(path),sha256=digest(path));report['schedule_traces'].append(parsed)
    report['schedule_trace']=report['schedule_traces'][-1] if report['schedule_traces'] else parse_schedule_trace(run_text,requested=schedule)
    report['counter_trace_requested']=counter
    report['counter_traces']=[]
    for reason,name,success in re.findall(r'^COUNTER_TRACE_FILE reason=(\w+) path=(counter-trace-\d+\.txt) success=([01])$',run_text,re.M):
        path=output/name
        if success!='1' or not path.is_file():continue
        parsed=parse_counter_trace(run_text+'\n'+path.read_text(encoding='utf-8',errors='replace'),requested=counter)
        parsed.update(reason=reason,path=str(path),sha256=digest(path));report['counter_traces'].append(parsed)
    report['counter_trace']=report['counter_traces'][-1] if report['counter_traces'] else parse_counter_trace(run_text,requested=counter)
    report['queue_watch'],report['queue_watches']=read_queue_watches(run_text,output,requested=counter)
    report['game_input_before']=root_before
    report['game_input_after']=inventory(root)
    report['game_input_unchanged']=report['game_input_before']==report['game_input_after'] and digest(args.xex)==XEX_SHA256
    gpu_paths=re.findall(r'^TITLE_GPU plugin_loaded backend=any presentation=false path=(.+)$',run_text,re.M)
    report['gpu_plugin_path_verified']=not args.gpu or (len(gpu_paths)==1 and Path(gpu_paths[0]).resolve()==output/'rexgpu-xenos.dll')
    for name in ('run.txt','title-sdk.log','host.map','title-natives.bin'):
        p=output/name
        if p.is_file():report[name]={'path':str(p),'sha256':digest(p),'size':p.stat().st_size}
    report['runtime_assets_unchanged']=result.get('runtime_assets_unchanged',True)
    report['panic_capture_requested']=capture_panic
    report['panic_capture']=parse_panic_capture(run_text)
    report['critical_section_capture_requested']=capture_critical
    report['critical_section_capture']=parse_critical_section_capture(run_text,requested=capture_critical)
    guarded = diagnostic_input_guards(result,report)
    report['diagnostic_success'] &= guarded
    report['bounded_observation'] &= guarded
    report['presentation']['initialized'] &= guarded
    if present and not (report['presentation']['loop_entered'] and report['presentation']['loop_exited']):
        report['bounded_observation']=False
    if present and not report['presentation']['initialized']:
        report['diagnostic_success']=False
        report['bounded_observation']=False
    if trace and not report['event_trace']['capture_verified']:report['bounded_observation']=False
    if schedule and not report['schedule_trace']['capture_verified']:
        report['bounded_observation']=False;report['diagnostic_success']=False
    if counter and not report['queue_watch']['capture_verified']:
        report['bounded_observation']=False;report['diagnostic_success']=False
    if counter and not report['counter_trace']['capture_verified']:
        report['bounded_observation']=False;report['diagnostic_success']=False
    (output/'title-entry.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f"TITLE_ENTRY resumed={report['guest_entrypoint_launched']} located={report['diagnostic_success']} game_boot=False",flush=True)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build-dir','generated','sdk','compiler','vcvars','xex','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--game-root',type=Path)
    parser.add_argument('--source',type=Path,default=Path('src/host/title_probe.cpp'))
    parser.add_argument('--observe-seconds',type=int,default=20,help='bounded diagnostic window, 20..60 seconds')
    parser.add_argument('--capture-critical-section',action='store_true',help='optional bounded read-only observation of the exact original SDK AV; absence is not failure')
    parser.add_argument('--capture-panic',action='store_true',help='opt-in bounded original-panic read-only observation; never resumes a fault')
    parser.add_argument('--trace-counter',action='store_true',help='transparent strong RAW hooks of original increment/reservation/decrement bodies')
    parser.add_argument('--trace-schedule',action='store_true',help='bounded transparent original delay/critical-section host-IAT observation')
    parser.add_argument('--trace-events',action='store_true',help='transparent scoped host IAT trace of four original SDK event imports')
    parser.add_argument('--present',action='store_true',help='bind a real hidden SDK window/presenter and pump the official UI loop')
    parser.add_argument('--gpu',action='store_true',help='request the unmodified SDK xenos plugin, no presentation')
    args=parser.parse_args(argv)
    try:
        if os.name!='nt':raise ValueError('title entry requires Windows SDK host')
        report=execute(args)
        if args.capture_critical_section and report['critical_section_capture']['status']=='invalid_capture':return 1
        if args.capture_panic and not report['panic_capture']['success']:return 1
        return 0 if report['diagnostic_success'] or report['bounded_observation'] else 1
    except (OSError,ValueError,KeyError) as error:
        print('TITLE_ENTRY_ERROR: '+str(error),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
