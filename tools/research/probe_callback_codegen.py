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


def profile_fields(profile):
    if profile == 'callback':
        return ENTRY, SIZE, RANGE_SHA256
    if profile == 'virtual-thunk':
        return 0x823C2740, 0x10, '0a315417a24fefd102c136c2b181f682cfa3b65422c9cbdaa146fd6caf719265'
    if profile == 'compare':
        return 0x82C1C1A0, 0x88, '60e3229fb7c29acb4ca50ea10e03bf77af7d9e361a9882d12b2f8e7e9ad3388f'
    if profile == 'native-gateway':
        return 0x82509380, 0x18, '24858452f74ebfe37c65055b81249f2b52a972d7f8374451f2b260775436bad2'
    if profile == 'extended-native':
        return 0x82517D70, 0x2C, 'b628e1746cfef4cd7c8340ad46cddaaf9fe16e6a083111c11983d7e43c6ce471'
    if profile == 'float-leaf':
        return 0x82AC1DE8, 0x14, '579d0af704a9e2c35ba6dc55ffe769344f780cf91ddc302e77aa72da6071ab53'
    if profile == 'bitfield-leaf':
        return 0x82AC2810, 0x20, '9174c77a101ea25e91a9fb0f1b8c9c7e512c4b7fdc7d80af0ce39fbfbe311f6a'
    if profile == 'conditional-tail':
        return 0x826A9EC8, 0x20, '8b4df364b42994f970049966b3a8c5db4528bc3c6a18c3f7cd2a78b35d0501a7'
    if profile == 'indexed-tail':
        return 0x82A3DEA0, 0x48, 'da78cc530445e6be3717bc6cec9e6cf949e163d65dc481ee5d6f63d4648b708a'
    if profile == 'word-leaf':
        return 0x82B7CCD0, 0x8, 'bbf1454f181f2d9d96316fad7d3c753d45df4678c1bafd0fe0217f84fa9b906f'
    if profile == 'byte-flag-leaf':
        return 0x82E078C0, 0xC, '647f0e9b625de7198c3695d9dc3bda6707c347a543408d0d1f510d4baed5fa1c'
    raise ValueError('unknown entry discovery profile')


def verify_hint(image, text, profile='callback'):
    entry, size, range_hash = profile_fields(profile)
    expected = {'functions': {f'0x{entry:08X}': {'size': size}}}
    if tomllib.loads(text) != expected:
        raise ValueError('callback hint must contain only the verified entry and size')
    code = image[entry-BASE:entry-BASE+size]
    if len(code) != size or hashlib.sha256(code).hexdigest() != range_hash:
        raise ValueError('original callback range hash mismatch')
    return {'entry': entry, 'size': size, 'range_sha256': range_hash}


def verify_entry(generated, entry=ENTRY):
    """Require a real generated body and an exact one-to-one registration."""
    generated = Path(generated)
    bodies = []
    for p in generated.glob('*recomp.*.cpp'):
        text = p.read_text(encoding='utf-8')
        bodies.extend((p, m[0]) for m in re.finditer(rf'DEFINE_REX_FUNC\(sub_{entry:08X}\) \{{.*?\n\}}',text,re.S))
    if len(bodies) != 1 or 'REX_FATAL' in bodies[0][1]:
        raise ValueError('expected one real generated callback body without fatal')
    register = (generated/'mc2_probe_register.cpp').read_text(encoding='utf-8')
    expected = re.findall(rf'registrar->SetFunction\(0x{entry:08X},\s*sub_{entry:08X}\);',register)
    if len(expected) != 1:
        raise ValueError('expected exact callback function registration')
    p, body = bodies[0]
    return dict(source=p.name,source_sha256=digest(p),body_sha256=hashlib.sha256(body.encode()).hexdigest(),registered=True)


def execute(args):
    xex, exe, output = args.xex.resolve(), args.sdk_exe.resolve(), args.output.resolve()
    hints = [ROOT/'research/xex/disc1-control-flow.toml', ROOT/'research/xex/disc1-callback-entry.toml']
    profile = getattr(args, 'entry_profile', 'callback')
    profile_fields(profile)
    if profile in ('virtual-thunk','compare','native-gateway','extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):hints.append(ROOT/'research/xex/disc1-virtual-thunk.toml')
    if profile in ('compare','native-gateway','extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):hints.append(ROOT/'research/xex/disc1-compare-callback.toml')
    if profile in ('native-gateway','extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):hints.append(ROOT/'research/xex/disc1-native-gateway.toml')
    if profile in ('extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):hints.append(ROOT/'research/xex/disc1-extended-native.toml')
    if profile in ('float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):hints.append(ROOT/'research/xex/disc1-float-leaf.toml')
    if profile in ('bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):hints.append(ROOT/'research/xex/disc1-bitfield-leaf.toml')
    if profile in ('conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):hints.append(ROOT/'research/xex/disc1-conditional-tail.toml')
    if profile in ('indexed-tail','word-leaf','byte-flag-leaf'):hints.append(ROOT/'research/xex/disc1-indexed-tail.toml')
    if profile in ('word-leaf','byte-flag-leaf'):hints.append(ROOT/'research/xex/disc1-word-leaf.toml')
    if profile == 'byte-flag-leaf':hints.append(ROOT/'research/xex/disc1-byte-flag-leaf.toml')
    before = {str(p): digest(p) for p in [xex, exe, args.loader_source.resolve(), *hints]}
    if before[str(xex)] != XEX_SHA256 or before[str(exe)] != SDK_EXE_SHA256:
        raise ValueError('unsupported XEX or SDK executable')
    image = image_from_xex(xex.read_bytes(), args.loader_source)
    proof = verify_hint(image, hints[1].read_text(encoding='utf-8'))
    if profile in ('virtual-thunk','compare','native-gateway','extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['virtual_thunk'] = verify_hint(image,hints[2].read_text(encoding='utf-8'),'virtual-thunk')
    if profile in ('compare','native-gateway','extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['compare'] = verify_hint(image,hints[3].read_text(encoding='utf-8'),'compare')
    if profile in ('native-gateway','extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['native_gateway'] = verify_hint(image,hints[4].read_text(encoding='utf-8'),'native-gateway')
    if profile in ('extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['extended_native'] = verify_hint(image,hints[5].read_text(encoding='utf-8'),'extended-native')
    if profile in ('float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['float_leaf'] = verify_hint(image,hints[6].read_text(encoding='utf-8'),'float-leaf')
    if profile in ('bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['bitfield_leaf'] = verify_hint(image,hints[7].read_text(encoding='utf-8'),'bitfield-leaf')
    if profile in ('conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['conditional_tail'] = verify_hint(image,hints[8].read_text(encoding='utf-8'),'conditional-tail')
    if profile in ('indexed-tail','word-leaf','byte-flag-leaf'):proof['indexed_tail'] = verify_hint(image,hints[9].read_text(encoding='utf-8'),'indexed-tail')
    if profile in ('word-leaf','byte-flag-leaf'):proof['word_leaf'] = verify_hint(image,hints[10].read_text(encoding='utf-8'),'word-leaf')
    if profile == 'byte-flag-leaf':proof['byte_flag_leaf'] = verify_hint(image,hints[11].read_text(encoding='utf-8'),'byte-flag-leaf')
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
        text = text.replace('includes = []', 'includes = '+json.dumps([p.name for p in hints]))
        manifest.write_text(text, encoding='utf-8')
        steps.append(run_step(exe,['--log-file',output/'codegen.log','codegen',manifest],output,'codegen',1200))
        if steps[-1]['returncode'] == 0:
            proof.update(verify_generated(project/'generated/default-disc1'))
            proof['callback'] = verify_entry(project/'generated/default-disc1')
            if profile in ('virtual-thunk','compare','native-gateway','extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['virtual_thunk']['generated'] = verify_entry(project/'generated/default-disc1',0x823C2740)
            if profile in ('compare','native-gateway','extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['compare']['generated'] = verify_entry(project/'generated/default-disc1',0x82C1C1A0)
            if profile in ('native-gateway','extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['native_gateway']['generated'] = verify_entry(project/'generated/default-disc1',0x82509380)
            if profile in ('extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['extended_native']['generated'] = verify_entry(project/'generated/default-disc1',0x82517D70)
            if profile in ('float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['float_leaf']['generated'] = verify_entry(project/'generated/default-disc1',0x82AC1DE8)
            if profile in ('bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['bitfield_leaf']['generated'] = verify_entry(project/'generated/default-disc1',0x82AC2810)
            if profile in ('conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'):proof['conditional_tail']['generated'] = verify_entry(project/'generated/default-disc1',0x826A9EC8)
            if profile in ('indexed-tail','word-leaf','byte-flag-leaf'):proof['indexed_tail']['generated'] = verify_entry(project/'generated/default-disc1',0x82A3DEA0)
            if profile in ('word-leaf','byte-flag-leaf'):proof['word_leaf']['generated'] = verify_entry(project/'generated/default-disc1',0x82B7CCD0)
            if profile == 'byte-flag-leaf':proof['byte_flag_leaf']['generated'] = verify_entry(project/'generated/default-disc1',0x82E078C0)
    stable = before == {p:digest(Path(p)) for p in before} and digest(output/'default-disc1.xex') == XEX_SHA256
    report = dict(profile=profile,proof=proof,steps=steps,input_hashes=before,inputs_unchanged=stable,
                  success=stable and steps[-1]['returncode']==0,game_execution='NOT TESTED')
    (output/'callback-codegen.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('CALLBACK_CODEGEN success='+str(report['success']))
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('xex','sdk-exe','loader-source','output'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--entry-profile',choices=('callback','virtual-thunk','compare','native-gateway','extended-native','float-leaf','bitfield-leaf','conditional-tail','indexed-tail','word-leaf','byte-flag-leaf'),default='callback')
    args=p.parse_args(argv)
    return 0 if execute(args)['success'] else 1


if __name__=='__main__':raise SystemExit(main())
