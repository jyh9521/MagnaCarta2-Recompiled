"""Stream explicitly selected, hash-verified ISO members into a new local root."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat

CHUNK = 1024*1024
RECORD = '.staging.json'


def hash_file(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        while data:=handle.read(CHUNK):digest.update(data)
    return digest.hexdigest()


def member_path(value):
    if not isinstance(value,str) or not value or '\\' in value:
        raise ValueError('member path must be nonempty forward-slash relative path')
    parts=value.split('/')
    for part in parts:
        if not part or part in ('.','..') or part.endswith((' ','.')):
            raise ValueError('invalid path component')
        if re.search(r'[\x00-\x1f<>:"|?*]',part) or part.split('.')[0].upper() in {
            'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
            raise ValueError('illegal Windows path component')
    return Path(*parts)


def regular(path):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):
        raise ValueError('input must be a regular non-link file')
    return info


def no_link_parents(path):
    for component in (path,*path.parents):
        if component.exists() or component.is_symlink():
            if component.is_symlink() or (hasattr(component,'is_junction') and component.is_junction()):
                raise ValueError('linked output ancestor')


def identity(path):
    info=regular(path)
    return (info.st_size,info.st_mtime_ns,info.st_dev,info.st_ino)


def plan(manifest,source,members,renames):
    if (not isinstance(manifest,dict) or type(manifest.get('schema_version'))!=int or
        manifest['schema_version']!=1 or manifest.get('errors')!=[] or
        not isinstance(manifest.get('files'),list)):
        raise ValueError('invalid or incomplete inventory')
    files=manifest['files']
    if any(not isinstance(row,dict) or not isinstance(row.get('path'),str) for row in files):
        raise ValueError('invalid inventory row')
    roots=[record for record in files if '::' not in record.get('path','')]
    if len(roots)!=1:
        raise ValueError('expected one ISO root record')
    root=roots[0]
    if root.get('offset')!=0 or root.get('type')!='xdvdfs' or root.get('size')!=source.stat().st_size:
        raise ValueError('ISO root record mismatch')
    if not re.fullmatch('[0-9a-f]{64}',str(root.get('sha256',''))):
        raise ValueError('invalid ISO hash')
    inventory={}
    for record in files:
        if '::' not in record.get('path',''):continue
        prefix,name=record['path'].split('::',1)
        if prefix!=root['path']:raise ValueError('member belongs to another ISO')
        if name in inventory:raise ValueError('duplicate inventory member')
        inventory[name]=record
    if not members or len(members)!=len(set(members)):
        raise ValueError('explicit unique member selection required')
    if set(renames)-set(members):raise ValueError('rename references unselected member')
    outputs=set();selected=[]
    for name in members:
        member_path(name)
        if name not in inventory:raise ValueError('selected member missing from inventory')
        record=inventory[name]
        target=renames.get(name,name);member_path(target)
        folded=target.casefold()
        if folded==RECORD.casefold() or folded.startswith(RECORD.casefold()+'/') or folded in outputs or any(
                folded.startswith(old+'/') or old.startswith(folded+'/') for old in outputs):
            raise ValueError('output path collision')
        outputs.add(folded)
        offset,size=record.get('offset'),record.get('size')
        if type(offset)!=int or type(size)!=int or offset<0 or size<0 or offset+size>root['size']:
            raise ValueError('invalid member range')
        if not re.fullmatch('[0-9a-f]{64}',str(record.get('sha256',''))):
            raise ValueError('invalid member hash')
        selected.append({'member':name,'output':target,'offset':offset,'size':size,'expected_sha256':record['sha256']})
    return root,selected


def stage(source,inventory,output,members,renames=None):
    source=Path(source).absolute();inventory=Path(inventory).absolute();output=Path(output).absolute()
    regular(source);regular(inventory);no_link_parents(source);no_link_parents(inventory);no_link_parents(output)
    if output.exists():raise ValueError('output directory already exists')
    if not output.parent.is_dir():raise ValueError('output parent must exist')
    before={str(p):identity(p) for p in (source,inventory)}
    inventory_hash=hash_file(inventory)
    root,selected=plan(json.loads(inventory.read_text(encoding='utf-8-sig')),source,members,renames or {})
    output.mkdir(exist_ok=False)
    report={'schema_version':1,'status':'in-progress','source':str(source),'inventory':str(inventory),
            'inventory_sha256':inventory_hash,'expected_iso_sha256':root['sha256'],
            'members':selected,'output':str(output)}
    record=output/RECORD
    def save():
        no_link_parents(output)
        if record.exists() and (record.is_symlink() or record.stat().st_nlink!=1):
            raise ValueError('staging record replaced by link')
        record.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    try:
        save()
        report['actual_iso_sha256']=hash_file(source)
        if report['actual_iso_sha256']!=root['sha256']:raise ValueError('ISO hash mismatch')
        with source.open('rb') as handle:
            for item in selected:
                target=output/member_path(item['output']);no_link_parents(target)
                target.parent.mkdir(parents=True,exist_ok=True);no_link_parents(target)
                handle.seek(item['offset']);remaining=item['size'];digest=hashlib.sha256()
                with target.open('xb') as writer:
                    while remaining:
                        data=handle.read(min(CHUNK,remaining))
                        if not data:raise ValueError('truncated member read')
                        writer.write(data);digest.update(data);remaining-=len(data)
                item['actual_sha256']=digest.hexdigest()
                if target.stat().st_nlink!=1:raise ValueError('output has hard links')
                if item['actual_sha256']!=item['expected_sha256']:raise ValueError('member hash mismatch')
                if hash_file(target)!=item['expected_sha256']:raise ValueError('reopened member hash mismatch')
                item['verified']=True;save()
        if any(identity(p)!=before[str(p)] for p in (source,inventory)) or hash_file(inventory)!=inventory_hash:
            raise ValueError('input changed during staging')
        report['inputs_unchanged']=True;report['status']='verified';save()
        return report
    except Exception as error:
        report['status']='failed';report['error']=f'{type(error).__name__}: {error}';save()
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ('iso','inventory','output'):parser.add_argument('--'+option,type=Path,required=True)
    parser.add_argument('--member',action='append',required=True)
    parser.add_argument('--rename',action='append',default=[],metavar='MEMBER=OUTPUT')
    args=parser.parse_args(argv);renames={}
    for item in args.rename:
        source,separator,target=item.partition('=')
        if not separator or not target or source in renames:raise ValueError('invalid or duplicate rename')
        renames[source]=target
    result=stage(args.iso,args.inventory,args.output,args.member,renames)
    print(f"STAGING members={len(result['members'])} iso_hash=verified member_hashes=verified inputs_unchanged=1 status=verified")
    return 0


if __name__=='__main__':raise SystemExit(main())
