"""Build/run a finite hidden real SDK presenter; no XEX or generated module."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from tools.research.compile_module import digest,inventory,vc_environment
from tools.research.probe_route_a import CLANG_CL_SHA256
from tools.research.link_module import runtime_path

ROOT=Path(__file__).resolve().parents[2]
PLUGIN_SHA256='0c23cfa23fc4fa5638dc8a3dc0de87b1041d97705d4677774083f1f350cd8d89'
RUNTIME_SHA256='e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a'


def verify_sdk_identity(sdk):
    """Fail before output creation/build for unsupported shipped DLLs."""
    if digest(sdk/'bin/rexgpu-xenos.dll')!=PLUGIN_SHA256 or digest(sdk/'bin/rexruntime.dll')!=RUNTIME_SHA256:
        raise ValueError('unsupported GPU/runtime identity')


def verify_host_compiler(compiler):
    if os.name!='nt' or digest(compiler)!=CLANG_CL_SHA256:
        raise ValueError('unsupported compiler/platform')


def validate_output(text):
    expected=['PRESENTER_SCOPE xex_loaded=0 guest_gpu_setup=0 game_assets=0',
              'PRESENTER_PLUGIN abi=1 backend=any','PRESENTATION_CONTEXT initialized=1 ui_thread=1',
              'PRESENTATION_SETUP status=00000000 has_presentation=1 presenter=1',
              'PRESENTATION_WINDOW open=1 hidden=1 binding_requested=1',
              'PRESENTATION_LOOP enter=1','PRESENTATION_LOOP exit=0',
              'PRESENTATION_WINDOW_CLOSED closed=1 native_destroyed=1',
              'PRESENTER_SHUTDOWN clean=1 loop_status=0']
    lines=[line for line in text.splitlines() if line.startswith(('PRESENTER_','PRESENTATION_'))]
    if lines!=expected:raise ValueError('presenter lifecycle differs from hidden window/binding-request/cleanup proof')
    return True


def command(compiler,sdk,output,source=ROOT/'src/host/presenter_probe.cpp'):
    return [str(Path(compiler).resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8','/O2','/DSPDLOG_FMT_EXTERNAL',
            '/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/EHa','/MD','/I'+str((Path(sdk)/'include').resolve()),
            '/I'+str((ROOT/'src/host').resolve()),str(source.resolve()),'/Fo'+str((output/'presenter.obj').resolve()),
            '/Fe'+str((output/'presenter.exe').resolve()),'/link','/Brepro','/LIBPATH:'+str((Path(sdk)/'lib').resolve()),
            'rexruntime.lib','spdlog.lib','fmt.lib','user32.lib','dxgi.lib','dxguid.lib']


def run_record(argv,output,label,env,timeout,hidden=False):
    record={'command':list(map(str,argv)),'cwd':str(output),'stdin':'DEVNULL','hidden_startup':hidden}
    options={}
    if hidden and os.name=='nt':
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        options={'startupinfo':startup,'creationflags':subprocess.CREATE_NO_WINDOW}
    start=time.monotonic()
    with (output/(label+'.txt')).open('x',encoding='utf-8') as log:
        try:record['exit_status']=subprocess.run(argv,cwd=output,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,**options).returncode
        except subprocess.TimeoutExpired:log.write('\nPRESENTER_PROCESS_TIMEOUT\n');record['exit_status']=124
        except OSError as error:log.write(str(error)+'\n');record['exit_status']=127
    record['elapsed_seconds']=round(time.monotonic()-start,3);record['log_sha256']=digest(output/(label+'.txt'))
    (output/(label+'.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return record


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('sdk','compiler','vcvars','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--duration-ms',type=int,default=500)
    args=parser.parse_args(argv)
    if not 100<=args.duration_ms<=5000:raise ValueError('duration must be100..5000ms')
    verify_host_compiler(args.compiler)
    sdk=args.sdk.resolve();output=args.output.absolute();source=ROOT/'src/host/presenter_probe.cpp';header=ROOT/'src/host/presentation_probe.h'
    if output==sdk or sdk in output.parents or output==source.parent or source.parent in output.parents:raise ValueError('output overlaps inputs')
    verify_sdk_identity(sdk)
    dependencies=[source,header,args.compiler,args.vcvars,sdk/'bin/rexruntime.dll',sdk/'bin/rexgpu-xenos.dll',
                  sdk/'lib/rexruntime.lib',sdk/'lib/spdlog.lib',sdk/'lib/fmt.lib']
    hashes={str(path):digest(path) for path in dependencies};trees=[sdk/'include',args.compiler.resolve().parent.parent/'lib/clang/20/include'];before=[inventory(path) for path in trees]
    output.mkdir(parents=True,exist_ok=False)
    report={'schema':1,'inputs':hashes,'header_trees':before,'scope':'real SDK presenter and hidden HWND, binding requested through public SetPresenter; no public surface getter, no XEX, guest GPU, generated module, assets or first-frame acceptance','duration_ms':args.duration_ms,'success':False}
    try:
        env=vc_environment(args.vcvars.resolve());build=run_record(command(args.compiler,sdk,output),output,'build',env,600)
        report['build']=build
        if build['exit_status']==0:
            shutil.copy2(sdk/'bin/rexgpu-xenos.dll',output/'rexgpu-xenos.dll')
            env=runtime_path(env,sdk);env['MC2_PRESENTER_MS']=str(args.duration_ms)
            run=run_record([str((output/'presenter.exe').resolve()),'--headless=false'],output,'run',env,30,True);report['run']=run
            report['executable_sha256']=digest(output/'presenter.exe')
            if run['exit_status']==0:report['success']=validate_output((output/'run.txt').read_text(encoding='utf-8'))
        report['inputs_unchanged']=all(digest(p)==hashes[str(p)] for p in dependencies) and all(inventory(path)==old for path,old in zip(trees,before))
        if not report['inputs_unchanged']:raise ValueError('source/dependency inputs changed')
    except Exception as error:report.update(success=False,error=f'{type(error).__name__}: {error}');raise
    finally:(output/'presenter-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'PRESENTER standalone=1 success={report["success"]}')
    return 0 if report['success'] else 1


if __name__=='__main__':raise SystemExit(main())
