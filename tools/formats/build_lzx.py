"""Build the optional LZX adapter from a locked, user-visible libmspack checkout."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
COMMIT="55d501976171397ccd5d5a7a1ca7da065b1d9a06"
URL="https://github.com/kyz/libmspack.git"

def run(command, **kwargs):
    subprocess.run(command,check=True,**kwargs)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--workspace",type=Path,default=Path("local/analysis/phase2"));p.add_argument("--cc",default="cc");a=p.parse_args()
    root=a.workspace.resolve();root.mkdir(parents=True,exist_ok=True);upstream=root/"upstream"/"libmspack"
    if not upstream.exists():
        run(["git","clone","--no-checkout",URL,str(upstream)])
    # Detached exact checkout; never overwrite a non-clean source tree.
    dirty=subprocess.check_output(["git","-C",str(upstream),"status","--porcelain"],text=True)
    if dirty: raise RuntimeError("libmspack source tree is modified")
    run(["git","-C",str(upstream),"fetch","origin",COMMIT]);run(["git","-C",str(upstream),"checkout","--detach",COMMIT])
    actual=subprocess.check_output(["git","-C",str(upstream),"rev-parse","HEAD"],text=True).strip()
    if actual!=COMMIT: raise RuntimeError("upstream commit mismatch")
    source=upstream/"libmspack"/"mspack";bridge=Path(__file__).resolve().with_name("lzx_bridge.c")
    if sys.platform=="win32":
        output=root/"ue3_lzx.dll"
        finder=Path("C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe")
        vs=subprocess.check_output([str(finder),"-latest","-products","*","-requires","Microsoft.VisualStudio.Component.VC.Tools.x86.x64","-property","installationPath"],text=True).strip()
        setup=Path(vs)/"VC"/"Auxiliary"/"Build"/"vcvars64.bat"
        if not setup.is_file(): raise RuntimeError("MSVC build tools not found")
        command=f'call "{setup}" >nul && cl /nologo /LD /O2 /I"{source}" "{bridge}" "{source / "lzxd.c"}" /link /OUT:"{output}"'
        batch=root/"build-lzx.cmd"
        batch.write_text("@echo off\n"+command+"\n",encoding="utf-8")
        run(f'cmd /d /c ""{batch}""',cwd=root)
    else:
        output=root/("libue3_lzx.dylib" if sys.platform=="darwin" else "libue3_lzx.so")
        run([a.cc,"-shared","-fPIC","-O2","-I",str(source),str(bridge),str(source/"lzxd.c"),"-o",str(output)],cwd=root)
    print(json.dumps({"library":str(output),"upstream":URL,"commit":COMMIT,"license":"LGPL-2.1","bridge":"project MIT; separate runtime library"}))
if __name__=="__main__":main()
