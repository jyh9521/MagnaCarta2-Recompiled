"""Guarded original event-import direct-call registry; no hooks or entry hints.

Caller-LR matching corroborates one original call site. Runtime handle identity,
return status, event state and producer identity require separate trace evidence.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct

BASE = 0x82000000
IMAGE_SHA256 = 'd18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9'
SDK_SHA256 = 'e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a'
IMPORTS = {
    'NtCreateEvent': (0xD1, 0x82E8DEDC),
    'NtWaitForSingleObjectEx': (0xFD, 0x82E8DF9C),
    'KeResetEvent': (0x8F, 0x82E8E32C),
    'KeSetEvent': (0x9D, 0x82E8E33C),
    'KeWaitForSingleObject': (0xB0, 0x82E8E36C),
    'NtPulseEvent': (0xE2, 0x82E8E5BC),
    'NtSetEvent': (0xF6, 0x82E8E5DC),
    'NtClearEvent': (0xCE, 0x82E8E5EC),
}
ARGUMENTS = {
    'NtCreateEvent': ['out_handle_BE32_pointer','object_attributes_pointer','event_type_0_manual_1_auto_request','initial_state_nonzero_true'],
    'NtWaitForSingleObjectEx': ['handle','processor_mode','alertable','timeout_BE64_pointer_or_null'],
    'KeResetEvent': ['guest_event_pointer'],
    'KeSetEvent': ['guest_event_pointer','priority_increment','wait'],
    'KeWaitForSingleObject': ['guest_object_pointer','wait_reason','processor_mode','alertable','timeout_BE64_pointer_or_null'],
    'NtPulseEvent': ['handle','previous_state_BE32_pointer_or_null'],
    'NtSetEvent': ['handle','previous_state_BE32_pointer_or_null'],
    'NtClearEvent': ['handle'],
}


def sha(data):return hashlib.sha256(data).hexdigest()


def branch(address, word):
    if word >> 26 != 18 or not word & 1:return None
    delta=word & 0x3FFFFFC
    if delta & 0x2000000:delta-=0x4000000
    return (delta if word & 2 else address+delta) & 0xFFFFFFFF


def scan_direct_calls(code, base, targets, pdata=()):
    """Pure bounded PPC direct-BL scanner, suitable for synthetic fixtures."""
    if type(base) is not int or base<0 or base%4 or len(code)%4 or base+len(code)>0x100000000:
        raise ValueError('invalid aligned code range')
    records=[]
    for offset in range(0,len(code),4):
        word=struct.unpack_from('>I',code,offset)[0]
        address=base+offset;target=branch(address,word)
        if target not in targets:continue
        name=targets[target]
        bounds=[{'entry':a,'end_exclusive':end,'size':end-a,'evidence':'original-PDATA'} for a,end in pdata if a<=address<end]
        if len(bounds)>1:raise ValueError('ambiguous containing PDATA ranges')
        context_start=max(0,offset-24);context=code[context_start:offset+4]
        records.append({'import_name':name,'thunk':target,'call':address,'caller_lr':address+4,
                        'instruction_hex':f'{word:08X}','instruction_sha256':sha(code[offset:offset+4]),
                        'context':{'start':base+context_start,'size':len(context),'sha256':sha(context)},
                        'function_boundary':bounds[0] if bounds else {'evidence':'unknown-no-containing-PDATA'},
                        'execution':'NOT-ESTABLISHED-BY-STATIC-SCAN'})
    return records


def pe_sections(image):
    if len(image)<64 or image[:2]!=b'MZ':raise ValueError('invalid DOS header')
    pe=struct.unpack_from('<I',image,0x3C)[0]
    if pe+24>len(image) or image[pe:pe+4]!=b'PE\0\0':raise ValueError('invalid PE header')
    count=struct.unpack_from('<H',image,pe+6)[0];optional=struct.unpack_from('<H',image,pe+20)[0]
    if not 0<count<=96 or optional<96 or pe+24+optional+count*40>len(image):raise ValueError('invalid section table')
    sections=[]
    for index in range(count):
        offset=pe+24+optional+40*index;size,rva,raw_size,raw_offset=struct.unpack_from('<4I',image,offset+8)
        flags=struct.unpack_from('<I',image,offset+36)[0]
        sections.append({'rva':rva,'size':size,'raw_size':raw_size,'raw_offset':raw_offset,'flags':flags})
    return pe,sections


def verify_imports(image, metadata, register):
    if not isinstance(metadata,dict) or not isinstance(metadata.get('import_libraries'),list):raise ValueError('invalid XEX import metadata')
    if any(not isinstance(library,dict) for library in metadata['import_libraries']):raise ValueError('invalid import library row')
    libraries=[library for library in metadata['import_libraries'] if library.get('name')=='xboxkrnl.exe']
    if len(libraries)!=1 or not isinstance(libraries[0].get('import_record_addresses'),list):raise ValueError('missing unique xboxkrnl library')
    addresses=libraries[0]['import_record_addresses'];result=[]
    for name,(ordinal,address) in IMPORTS.items():
        if addresses.count(address)!=1:raise ValueError('missing/duplicate original import record: '+name)
        offset=address-BASE
        expected=struct.pack('>4I',0x01010000|ordinal,0x02010000|ordinal,0x7D6903A6,0x4E800420)
        if not 0<=offset<=len(image)-16 or image[offset:offset+16]!=expected:raise ValueError('original import thunk bytes mismatch: '+name)
        pattern=rf'registrar->SetFunction\(0x{address:08X},\s*__imp__{name}\);'
        if len(re.findall(pattern,register))!=1:raise ValueError('generated import name mismatch: '+name)
        result.append({'name':name,'library':'xboxkrnl.exe','ordinal':ordinal,'thunk':address,
                       'original_bytes_hex':expected.hex(),'range_sha256':sha(expected),
                       'argument_registers':{f'r{i+3}':value for i,value in enumerate(ARGUMENTS[name])},
                       'result':'raw return; do not infer signal state from this registry'})
    return result


def seal_registry(result):
    result=dict(result)
    result['registry_sha256']=sha(json.dumps(result,sort_keys=True,separators=(',',':')).encode())
    return result


def build_registry(image, xex_metadata, generated_register_text):
    if sha(image)!=IMAGE_SHA256:raise ValueError('unsupported original image SHA-256')
    imports=verify_imports(image,xex_metadata,generated_register_text)
    pe,sections=pe_sections(image)
    pdata_offset,pdata_size=struct.unpack_from('<II',image,pe+24+96+24)
    if pdata_size%8 or pdata_offset+pdata_size>len(image):raise ValueError('PDATA outside image')
    pdata=[]
    for entry,fields in struct.iter_unpack('>II',image[pdata_offset:pdata_offset+pdata_size]):
        size=((fields>>8)&0x3FFFFF)*4
        if size:pdata.append((entry,entry+size))
    targets={address:name for name,(ordinal,address) in IMPORTS.items()};calls=[]
    for section in sections:
        if not section['flags'] & 0x20000000:continue
        offset,size=section['rva'],section['size']
        if offset%4 or size%4 or offset+size>len(image):raise ValueError('invalid executable range')
        calls.extend(scan_direct_calls(image[offset:offset+size],BASE+offset,targets,pdata))
    for call in calls:
        bounds=call['function_boundary']
        if bounds['evidence']=='original-PDATA':
            offset=bounds['entry']-BASE;size=bounds['size']
            if offset<0 or offset+size>len(image):raise ValueError('containing PDATA outside image')
            bounds['range_sha256']=sha(image[offset:offset+size])
    if len({r['caller_lr'] for r in calls})!=len(calls):raise ValueError('duplicate direct call LR')
    return seal_registry({'schema_version':1,'profile':'MC2-original-event-import-direct-calls',
                          'image_sha256':IMAGE_SHA256,'generated_register_sha256':sha(generated_register_text.encode()),
                          'imports':imports,'direct_calls':calls,'call_counts':dict(Counter(r['import_name'] for r in calls)),
                          'limits':'direct original BL only; no indirect/native SDK internal caller recovery; no runtime producer inference'})


def match_caller_lr(registry, import_name, caller_lr):
    if not isinstance(import_name,str) or import_name not in IMPORTS:raise ValueError('unsupported event import name')
    if type(caller_lr) is not int or not 4<=caller_lr<=0xFFFFFFFF or caller_lr%4:raise ValueError('invalid caller LR')
    if not isinstance(registry,dict) or type(registry.get('schema_version')) is not int or registry.get('schema_version')!=1 or registry.get('profile')!='MC2-original-event-import-direct-calls' or registry.get('image_sha256')!=IMAGE_SHA256:
        raise ValueError('unsupported registry identity')
    body={key:value for key,value in registry.items() if key!='registry_sha256'}
    if seal_registry(body)['registry_sha256']!=registry.get('registry_sha256'):raise ValueError('registry integrity mismatch')
    matches=[row for row in registry['direct_calls'] if row['caller_lr']==caller_lr and row['import_name']==import_name]
    if len(matches)>1:raise ValueError('ambiguous original caller LR')
    return {'status':'validated-original-direct-call' if matches else 'unresolved-indirect-or-unlisted',
            'import_name':import_name,'caller_lr':caller_lr,'matched':matches[0] if matches else None,
            'limits':'matching establishes original call-site identity only, not event ownership or producer'}


def sdk_contracts(binary):
    if sha(binary)!=SDK_SHA256:raise ValueError('unsupported shipping SDK runtime SHA-256')
    pe,sections=pe_sections(binary)
    def offset(rva,size=1):
        for section in sections:
            start=section['rva'];raw=section['raw_offset']
            if start<=rva and rva+size<=start+section['raw_size'] and raw+rva-start+size<=len(binary):return raw+rva-start
        raise ValueError('SDK RVA outside raw sections')
    def string(rva):
        start=offset(rva);end=binary.find(b'\0',start,min(len(binary),start+4096))
        if end<0:raise ValueError('unterminated SDK export name')
        return binary[start:end].decode('ascii')
    export_rva,_=struct.unpack_from('<II',binary,pe+24+112);data=offset(export_rva,40)
    _,nfunc,nname,fr,nr,orr=struct.unpack_from('<6I',binary,data+16)
    if nfunc>100000 or nname>100000:raise ValueError('SDK export count exceeds limit')
    functions=struct.unpack_from('<'+str(nfunc)+'I',binary,offset(fr,nfunc*4));names=struct.unpack_from('<'+str(nname)+'I',binary,offset(nr,nname*4));ordinals=struct.unpack_from('<'+str(nname)+'H',binary,offset(orr,nname*2));exports=[]
    for i,rva in enumerate(names):
        if ordinals[i]>=nfunc:raise ValueError('SDK export ordinal range')
        name=string(rva)
        for expected in IMPORTS:
            if name.startswith('?'+expected+'_entry@xboxkrnl@kernel@rex@@'):
                address=functions[ordinals[i]];start=offset(address,32)
                exports.append({'name':expected,'decorated_export':name,'entry_rva':address,'entry_prefix_size':32,'entry_prefix_sha256':sha(binary[start:start+32])})
    if Counter(row['name'] for row in exports)!=Counter(IMPORTS.keys()):raise ValueError('missing/ambiguous SDK event entry exports')
    return {'runtime_sha256':SDK_SHA256,'event_entry_exports':exports,'abi_evidence':'pinned public threading.h signatures plus manually audited shipping entry code; raw return not a state query'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('xex','loader-source','generated-register','sdk-runtime','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(argv)
    inputs=[a.xex,a.loader_source,a.generated_register,a.sdk_runtime]
    if a.output.resolve() in [path.resolve() for path in inputs]:raise ValueError('output overlaps input')
    from tools.research.verify_branch_ranges import image_from_xex
    from tools.formats.xex import parse_xex
    xex=a.xex.read_bytes();image=image_from_xex(xex,a.loader_source)
    result=build_registry(image,parse_xex(xex),a.generated_register.read_text(encoding='utf-8-sig'))
    output={'registry':result,'sdk_contracts':sdk_contracts(a.sdk_runtime.read_bytes()),
            'input_sha256':{str(path):sha(path.read_bytes()) for path in inputs},'runtime_execution':'NOT-TESTED'}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as target:json.dump(output,target,indent=2);target.write('\n')
    print('EVENT_IMPORT_SITES '+json.dumps(result['call_counts'],sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
