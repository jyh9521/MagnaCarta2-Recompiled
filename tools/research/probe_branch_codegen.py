"""Reproduce strict PPC range correction without editing game/SDK bytes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.research.probe_route_a import prepare_input, run_step
from tools.research.verify_branch_ranges import image_from_xex, verify_image, verify_generated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("iso", "sdk-zip", "sdk-exe", "loader-source", "output"):
        parser.add_argument("--"+name, required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args(argv)
    if args.timeout < 1:
        raise ValueError("timeout must be positive")
    output = args.output.resolve()
    xex = prepare_input(args.iso, args.sdk_zip, args.sdk_exe, output)
    report = verify_image(image_from_xex(xex.read_bytes(), args.loader_source))
    project = output/"project"
    exe = args.sdk_exe.resolve()
    steps = [run_step(exe, ["--log-file", output/"init.log", "init", "--project-name", "mc2_probe",
                           "--xex-path", xex, "--project-root", project], output, "init", args.timeout)]
    if steps[-1]["returncode"] == 0:
        manifest = project/"mc2_probe_manifest.toml"
        text = manifest.read_text(encoding="utf-8")
        if text.count("includes = []") != 1:
            raise ValueError("unexpected manifest")
        shutil.copyfile(manifest, project/"manifest-before-ranges.toml")
        shutil.copyfile(ROOT/"research/xex/disc1-control-flow.toml", project/"control-flow.toml")
        manifest.write_text(text.replace("includes = []", 'includes = ["control-flow.toml"]'), encoding="utf-8")
        steps.append(run_step(exe, ["--log-file", output/"codegen.log", "codegen", manifest], output, "codegen", args.timeout))
        if steps[-1]["returncode"] == 0:
            report.update(verify_generated(project/"generated/default-disc1"))
    report.update(steps=steps, game_execution="NOT TESTED")
    with (output/"experiment.json").open("x", encoding="utf-8") as target:
        json.dump(report, target, indent=2)
        target.write("\n")
    print("BRANCH_CODEGEN " + json.dumps(report, sort_keys=True))
    return 0 if steps[-1]["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
