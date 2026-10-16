"""Strict regeneration with an original-image-verified indirect callback entry."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tomllib

from tools.research.probe_route_a import SDK_EXE_SHA256, XEX_SHA256, digest, run_step
from tools.research.verify_branch_ranges import BASE, image_from_xex, verify_generated

ROOT = Path(__file__).resolve().parents[2]
ENTRY = 0x8234FF10
SIZE = 0x30
RANGE_SHA256 = '5c43c892cc33dcb8b15d083257e0a8211788bb01aaa0698cd379c2164e77665e'


def verify_hint(image, text):
    expected = {'functions': {'0x8234FF10': {'size': SIZE}}}
    if tomllib.loads(text) != expected:
        raise ValueError('callback hint must contain only the verified entry and size')
    code = image[ENTRY-BASE:ENTRY-BASE+SIZE]
    if len(code) != SIZE or hashlib.sha256(code).hexdigest() != RANGE_SHA256:
        raise ValueError('original callback range hash mismatch')
    return {'entry': ENTRY, 'size': SIZE, 'range_sha256': RANGE_SHA256}


def verify_entry(generated):
    """Require a real generated body and an exact one-to-one registration."""
    generated = Path(generated)
    bodies = []
    for p in generated.glob('*recomp.*.cpp'):
        text = p.read_text(encoding='utf-8')
        bodies.extend((p, m[0]) for m in re.finditer(r'DEFINE_REX_FUNC\(sub_8234FF10\) \{.*?\n\}',text,re.S))
    if len(bodies) != 1 or 'REX_FATAL' in bodies[0][1]:
        raise ValueError('expected one real generated callback body without fatal')
    register = (generated/'mc2_probe_register.cpp').read_text(encoding='utf-8')
    expected = re.findall(r'registrar->SetFunction\(0x8234FF10,\s*sub_8234FF10\);',register)
    if len(expected) != 1:
        raise ValueError('expected exact callback function registration')
    p, body = bodies[0]
    return dict(source=p.name,source_sha256=digest(p),body_sha256=hashlib.sha256(body.encode()).hexdigest(),registered=True)


def execute(args):
    xex, exe, output = args.xex.resolve(), args.sdk_exe.resolve(), args.output.resolve()
    hints = [ROOT/'research/xex/disc1-control-flow.toml', ROOT/'research/xex/disc1-callback-entry.toml']
    before = {str(p): digest(p) for p in [xex, exe, args.loader_source.resolve(), *hints]}
    if before[str(xex)] != XEX_SHA256 or before[str(exe)] != SDK_EXE_SHA256:
        raise ValueError('unsupported XEX or SDK executable')
    image = image_from_xex(xex.read_bytes(), args.loader_source)
    proof = verify_hint(image, hints[1].read_text(encoding='utf-8'))
    for p in [xex, exe, args.loader_source.resolve(), *hints]:
        if output == p or output in p.parents or p.parent == output or p.parent in output.parents:
            raise ValueError('output overlaps an input')
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(xex, output/'default-disc1.xex')
    project = output/'project'
    steps = [run_step(exe, ['--log-file',output/'init.log','init','--project-name','mc2_probe',
                           '--xex-path',output/'default-disc1.xex','--project-root',project],output,'init',1200)]
    if steps[-1]['returncode'] == 0:
        manifest = project/'mc2_probe_manifest.toml'
        text = manifest.read_text(encoding='utf-8')
        if text.count('includes = []') != 1:
            raise ValueError('unexpected generated manifest')
        for p in hints: shutil.copy2(p, project/p.name)
        text = text.replace('includes = []', 'includes = ["disc1-control-flow.toml", "disc1-callback-entry.toml"]')
        manifest.write_text(text, encoding='utf-8')
        steps.append(run_step(exe,['--log-file',output/'codegen.log','codegen',manifest],output,'codegen',1200))
        if steps[-1]['returncode'] == 0:
            proof.update(verify_generated(project/'generated/default-disc1'))
            proof['callback'] = verify_entry(project/'generated/default-disc1')
    stable = before == {p:digest(Path(p)) for p in before} and digest(output/'default-disc1.xex') == XEX_SHA256
    report = dict(proof=proof,steps=steps,input_hashes=before,inputs_unchanged=stable,
                  success=stable and steps[-1]['returncode']==0,game_execution='NOT TESTED')
    (output/'callback-codegen.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('CALLBACK_CODEGEN success='+str(report['success']))
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('xex','sdk-exe','loader-source','output'):p.add_argument('--'+name,required=True,type=Path)
    args=p.parse_args(argv)
    return 0 if execute(args)['success'] else 1


if __name__=='__main__':raise SystemExit(main())
