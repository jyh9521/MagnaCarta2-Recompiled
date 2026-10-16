"""Reproduce a strict, hash-locked ReXGlue analysis (no game execution)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SDK_URL = "https://github.com/rexglue/rexglue-sdk/releases/download/v0.10.0/rexglue-sdk-0.10.0-win-amd64.zip"
SDK_ZIP_SHA256 = "ad4485da853fbe932e9f5dbb643f9b5fe85dc73775ebbad4df6879fe6df0c11b"
SDK_EXE_SHA256 = "04014c2e5eef3c40bddc490d413e910e5ba98d81aa3da1c1f5d43dd29728ee3a"
XEX_SHA256 = "26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f"
XEX_OFFSET = 3899768832
XEX_SIZE = 19611648
LLVM_URL = "https://github.com/llvm/llvm-project/releases/download/llvmorg-20.1.8/LLVM-20.1.8-win64.exe"
LLVM_PACKAGE_SHA256 = "3197846a2b19063687dd56e93e34cd941e3548d907f23a6131571321bdf9fe7b"
CLANG_CL_SHA256 = "57e32b1ea2456f12f97bf802453171bbff12d56b2c486b4eca0c75343c0cda2c"


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def prepare_input(iso, sdk_zip, sdk_exe, output):
    """Verify all supplied inputs before creating any output or invoking SDK."""
    if digest(sdk_zip) != SDK_ZIP_SHA256:
        raise ValueError("SDK ZIP SHA-256 mismatch")
    if digest(sdk_exe) != SDK_EXE_SHA256:
        raise ValueError("SDK executable SHA-256 mismatch")
    with Path(iso).open("rb") as source:
        source.seek(XEX_OFFSET)
        data = source.read(XEX_SIZE)
    if len(data) != XEX_SIZE or hashlib.sha256(data).hexdigest() != XEX_SHA256:
        raise ValueError("unsupported original XEX SHA-256/size")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    xex = output / "default-disc1.xex"
    with xex.open("xb") as target:
        target.write(data)
    return xex.resolve()


def run_step(exe, args, output, name, timeout):
    command = [str(exe), *map(str, args)]
    with (output / f"{name}-console.txt").open("x", encoding="utf-8") as log:
        try:
            result = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False)
            status = result.returncode
        except subprocess.TimeoutExpired:
            status = 124
            log.write(f"\nPROBE_TIMEOUT seconds={timeout}; process terminated\n")
    return {"command": command, "returncode": status, "console": f"{name}-console.txt"}


def verify_compiler(package, compiler):
    if digest(package) != LLVM_PACKAGE_SHA256:
        raise ValueError("LLVM package SHA-256 mismatch")
    if digest(compiler) != CLANG_CL_SHA256:
        raise ValueError("Clang compiler SHA-256 mismatch")


def compile_unit(compiler, vcvars, sdk_exe, generated, output, timeout):
    """Compile one real generated translation unit, never link or execute it."""
    source = generated / "mc2_probe_recomp.122.cpp"
    obj = output / "mc2_probe_recomp.122-clang.obj"
    sdk_include = sdk_exe.parent.parent / "include"
    command_file = output / "compile-one.cmd"
    command_file.write_text(
        f'@echo off\ncall "{vcvars}" >nul\n'
        f'"{compiler}" /nologo /c /Brepro /std:c++latest /utf-8 /DSPDLOG_FMT_EXTERNAL '
        f'/DSPDLOG_COMPILED_LIB /DNOMINMAX /DWIN32_LEAN_AND_MEAN /EHa /arch:AVX2 /bigobj /MD '
        f'/I"{sdk_include}" /I"{generated}" "{source}" /Fo"{obj}"\nexit /b %ERRORLEVEL%\n',
        encoding="utf-8")
    result = run_step(Path(os.environ.get("COMSPEC", "cmd.exe")),
                      ["/d", "/c", command_file], output, "compile", timeout)
    result["source_sha256"] = digest(source)
    if result["returncode"] == 0:
        result["object_size"] = obj.stat().st_size
        result["object_sha256"] = digest(obj)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--sdk-zip", type=Path, required=True)
    parser.add_argument("--sdk-exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new, non-existing local directory")
    parser.add_argument("--with-hints", action="store_true", help="also test the two recorded branch-target hypotheses")
    parser.add_argument("--timeout", type=int, default=900, help="per-step timeout in seconds")
    parser.add_argument("--compile-unit", action="store_true", help="compile one generated TU on Windows; no linking/execution")
    parser.add_argument("--llvm-package", type=Path)
    parser.add_argument("--compiler", type=Path, help="unpacked official clang-cl.exe")
    parser.add_argument("--vcvars", type=Path, help="installed VS2022 vcvars64.bat")
    args = parser.parse_args(argv)
    try:
        if args.timeout < 1:
            raise ValueError("timeout must be positive")
        if args.compile_unit:
            if os.name != "nt" or not all((args.llvm_package, args.compiler, args.vcvars)):
                raise ValueError("Windows compile requires --llvm-package, --compiler and --vcvars")
            verify_compiler(args.llvm_package, args.compiler)
            if not args.vcvars.is_file():
                raise ValueError("vcvars64.bat not found")
        exe, output = args.sdk_exe.resolve(), args.output.resolve()
        xex = prepare_input(args.iso, args.sdk_zip, exe, output)
        project = output / "project"
        steps = [run_step(exe, ["--log-file", output / "init.log", "init", "--project-name", "mc2_probe",
            "--xex-path", xex, "--project-root", project], output, "init", args.timeout)]
        manifest = project / "mc2_probe_manifest.toml"
        if steps[-1]["returncode"] == 0:
            steps.append(run_step(exe, ["--log-file", output / "baseline.log", "codegen", manifest],
                                  output, "baseline", args.timeout))
            if args.with_hints and steps[-1]["returncode"] != 124:
                shutil.copyfile(manifest, project / "mc2_probe_manifest-baseline.toml")
                shutil.copyfile(ROOT / "research/xex/disc1-entry-hints.toml", project / "hints-disc1.toml")
                text = manifest.read_text(encoding="utf-8")
                if text.count("includes = []") != 1:
                    raise ValueError("unexpected generated manifest: refusing automatic edit")
                manifest.write_text(text.replace("includes = []", 'includes = ["hints-disc1.toml"]'), encoding="utf-8")
                steps.append(run_step(exe, ["--log-file", output / "hinted.log", "codegen", manifest],
                                      output, "hinted", args.timeout))
            if args.compile_unit and steps[-1]["returncode"] == 0:
                steps.append(compile_unit(args.compiler.resolve(), args.vcvars.resolve(), exe,
                    project / "generated/default-disc1", output, args.timeout))
        summary = {"input_xex_sha256": XEX_SHA256, "sdk_zip_sha256": SDK_ZIP_SHA256,
                   "sdk_exe_sha256": SDK_EXE_SHA256, "sdk_url": SDK_URL, "steps": steps,
                   "game_execution": "NOT TESTED", "compiler_execution": "TESTED" if any(s["console"] == "compile-console.txt" for s in steps) else "NOT TESTED"}
        with (output / "experiment.json").open("x", encoding="utf-8") as target:
            json.dump(summary, target, indent=2)
            target.write("\n")
        status = steps[-1]["returncode"]
        print("ROUTE_A " + " ".join(f"{Path(s['console']).stem}={s['returncode']}" for s in steps))
        return 0 if status == 0 else 1
    except (OSError, ValueError) as exc:
        print(f"ROUTE_A_ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
