"""Reconcile a guarded historical static report with a runtime GNatives dump.

This checks observation metadata and computes a difference, not handler semantics.
It never executes code, changes a table, or creates entry hints.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

BASE = 0x82000000
IMAGE_SIZE = 20119552
IMAGE_SHA256 = 'd18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9'
XEX_SHA256 = '26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f'
GNATIVES = 0x83250D80
FALLBACK = 0x82505980
ENTRIES = 4096
CODE_RANGES = ((0x822D0000, 0x82E8EB9C), (0x82E8EC00, 0x82E9E5A4))


def sha(data):return hashlib.sha256(data).hexdigest()


def integer(value, lower, upper, label):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError('invalid '+label)
    return value


def code_address(value):
    integer(value, 0, 0xFFFFFFFF, 'code address')
    if value % 4 or not any(begin <= value < end for begin,end in CODE_RANGES):
        raise ValueError('address outside original executable sections')
    return value


def static_slots(document):
    if not isinstance(document,dict) or type(document.get('schema_version')) is not int or document.get('schema_version') != 1 or document.get('profile') != 'MC2-name-lookup-static':
        raise ValueError('unsupported static report schema/profile')
    if document.get('image_sha256') != IMAGE_SHA256 or type(document.get('base')) is not int or document['base'] != BASE or document.get('inputs_unchanged') is not True:
        raise ValueError('static image/input identity mismatch')
    rows=document.get('indexed_initializers')
    if not isinstance(rows,list) or len(rows) != 299:
        raise ValueError('expected historical 299 static initializers')
    summary=document.get('summary')
    if not isinstance(summary,dict) or type(summary.get('recovered_indexed_initializers')) is not int or summary.get('recovered_indexed_initializers') != len(rows) or type(summary.get('runtime_gnatives_address')) is not int or summary.get('runtime_gnatives_address') != GNATIVES:
        raise ValueError('static summary mismatch')
    result={};initializers=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('invalid initializer record')
        index=integer(row.get('native_index'),0,ENTRIES-1,'native index')
        if index in result:raise ValueError('duplicate static native index')
        init=code_address(row.get('initializer'))
        if init in initializers:raise ValueError('duplicate initializer address')
        initializers.add(init)
        target=code_address(row.get('implementation'))
        pointer=integer(row.get('source_pointer_slot'),BASE,BASE+IMAGE_SIZE-4,'source pointer slot')
        if pointer%4:raise ValueError('unaligned source pointer slot')
        expected={'destination':GNATIVES+index*4,'initialization_flag':0x8327B660,
                  'fallback':FALLBACK,'table_entries':ENTRIES,'duplicate_index_slot':0x83263F1C}
        if any(type(row.get(k)) is not int or row[k]!=v for k,v in expected.items()):
            raise ValueError('initializer profile fields mismatch')
        if row.get('status') != 'verified-instruction-template-not-executed' or not isinstance(row.get('instruction_sha256'),str) or re.fullmatch('[0-9a-f]{64}',row['instruction_sha256']) is None:
            raise ValueError('invalid initializer evidence')
        result[index]=target
    return result


def reconcile(static, dump, runtime, run, log, register=None):
    historical=static_slots(static)
    if len(dump) != ENTRIES*4:raise ValueError('runtime table must be exactly 16384 bytes')
    if not isinstance(runtime,dict) or type(runtime.get('schema')) is not int or runtime.get('schema') != 1:
        raise ValueError('unsupported runtime report schema')
    for field in ('image_loaded','guest_entrypoint_launched','inputs_unchanged','runtime_assets_unchanged','game_input_unchanged'):
        if runtime.get(field) is not True:raise ValueError('runtime provenance flag missing: '+field)
    image=runtime.get('image')
    if not isinstance(image,dict) or image.get('sha256') != XEX_SHA256:
        raise ValueError('runtime XEX identity mismatch')
    for key, data in (('title-natives.bin',dump),('run.txt',log)):
        meta=runtime.get(key)
        if not isinstance(meta,dict) or type(meta.get('size')) is not int or meta['size'] != len(data) or meta.get('sha256') != sha(data):
            raise ValueError('runtime artifact identity mismatch: '+key)
    status=integer(runtime.get('exit_status'),0,0xFFFFFFFF,'runtime exit status')
    if not isinstance(run,dict) or type(run.get('exit_status')) is not int or run['exit_status'] != status or run.get('log_sha256') != sha(log) or run.get('stdin') != 'DEVNULL':
        raise ValueError('runtime process/log identity mismatch')
    values=struct.unpack('>4096I',dump)
    if any(value%4 or not any(lo<=value<hi for lo,hi in CODE_RANGES) for value in values):
        raise ValueError('runtime slot outside original executable sections')
    natives=runtime.get('natives')
    expected={'guard':1,'bound':ENTRIES,'fallback':sum(v==FALLBACK for v in values),
              'int_const':values[0x1D],'add':values[0x92]}
    if not isinstance(natives,dict) or any(type(natives.get(k)) is not int or natives[k]!=v for k,v in expected.items()):
        raise ValueError('runtime native summary mismatch')
    line=(f"TITLE_NATIVES guard=1 bound=4096 fallback={expected['fallback']} "
          f"int_const={expected['int_const']:08X} add={expected['add']:08X}")
    text=log.decode('utf-8',errors='strict')
    if text.splitlines().count(line) != 1:raise ValueError('missing or duplicate native observation line')
    entries=None
    if register is not None:
        pairs=re.findall(r'registrar->SetFunction\(0x([0-9A-Fa-f]{8}),\s*sub_([0-9A-Fa-f]{8})\);',register)
        if not pairs or any(a.lower()!=b.lower() for a,b in pairs) or len({a.lower() for a,b in pairs})!=len(pairs):
            raise ValueError('unexpected generated registration template')
        entries={int(a,16) for a,b in pairs}
    active={i:v for i,v in enumerate(values) if v!=FALLBACK}
    missing=[{'index':i,'index_hex':f'{i:02X}','target':v,'target_hex':f'{v:08X}',
              'mapped':v in entries if entries is not None else None} for i,v in active.items() if i not in historical]
    mismatch=[{'index':i,'static':v,'runtime':values[i]} for i,v in historical.items() if values[i]!=v]
    return {'schema_version':1,'scope':'observed table versus historical initializer template; no handler execution proof',
            'image_sha256':IMAGE_SHA256,'xex_sha256':XEX_SHA256,'runtime_snapshot_sha256':sha(dump),
            'runtime_log_sha256':sha(log),'runtime_exit_status':status,'runtime_nonfallback_slots':len(active),
            'old_initializer_indices':len(historical),'missing_old_indices':missing,'old_runtime_mismatches':mismatch,
            'old_indices_not_active':[i for i in historical if i not in active],
            'automatic_hints_written':False,'individual_handler_execution':'NOT VERIFIED'}


def read_json(path):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('duplicate JSON field: '+key)
            result[key]=value
        return result
    if path.stat().st_size>64*1024*1024:raise ValueError('JSON input exceeds size limit')
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('static-report','snapshot','runtime-report','run-report','run-log','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--generated-register',type=Path)
    a=p.parse_args(argv)
    paths=[a.static_report,a.snapshot,a.runtime_report,a.run_report,a.run_log]
    if a.generated_register:paths.append(a.generated_register)
    if a.output.resolve() in [path.resolve() for path in paths]:raise ValueError('output overlaps input')
    if a.snapshot.stat().st_size != ENTRIES*4:raise ValueError('runtime table size mismatch')
    if a.run_log.stat().st_size>8*1024*1024:raise ValueError('runtime log exceeds size limit')
    register=None
    if a.generated_register:
        if a.generated_register.stat().st_size>8*1024*1024:raise ValueError('generated register exceeds size limit')
        register=a.generated_register.read_text(encoding='utf-8-sig')
    result=reconcile(read_json(a.static_report),a.snapshot.read_bytes(),read_json(a.runtime_report),read_json(a.run_report),a.run_log.read_bytes(),register)
    result['input_sha256']={str(path):sha(path.read_bytes()) for path in paths}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as target:json.dump(result,target,indent=2);target.write('\n')
    print(f"NATIVE_SLOT_RECONCILIATION runtime={result['runtime_nonfallback_slots']} static={result['old_initializer_indices']} missing={len(result['missing_old_indices'])} mismatches={len(result['old_runtime_mismatches'])}")
    return 0


if __name__=='__main__':raise SystemExit(main())
