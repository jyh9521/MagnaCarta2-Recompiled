"""Strict bounded RAW call intervals, not rendered frames or a complete guest trace."""
import hashlib
import re
from pathlib import Path
from statistics import median
TARGETS=(0x8277B6D8,0x8244A360,0x8286E618,0x82E20568,0x82399778)
HEX={'target','context','lr','sp','result'}|{f'r{i}'for i in range(3,11)}

def fields(line):
    row={}
    for token in line.split()[1:]:
        key,sep,value=token.partition('=')
        if not sep or not value or key in row:raise ValueError('malformed/duplicate field')
        if key in {'status','phase'}:row[key]=value;continue
        base=16 if key in HEX else 10
        if not re.fullmatch('[0-9A-Fa-f]{1,16}'if base==16 else'[0-9]{1,20}',value):raise ValueError('invalid number')
        row[key]=int(value,base)
        if row[key]>=2**64:raise ValueError('overflow')
    return row

def parse_frame_timeline(text,requested=False):
    result=dict(status='disabled'if not requested else'invalid_capture',capture_verified=False,errors=[],targets=[],entries=[],pending=[],completed_calls=[],incomplete_calls=[],intervals=[],coverage_complete=False,visible_frame_proof=False,scope='Native GetTickCount64 intervals include observation/scheduling overhead; TLS nesting is not a complete guest call graph. Frozen weak snapshots are not quiescence.')
    if not requested:return result
    try:
        lines=text.splitlines()
        if [x for x in lines if x.startswith('TITLE_WAIT_SDK')]!=['TITLE_WAIT_SDK parent_attested=1']:raise ValueError('SDK attestation')
        if [x for x in lines if x.startswith('TITLE_FRAME_TIMELINE')]!=['TITLE_FRAME_TIMELINE enabled=1 code_guard=1 binding_guard=1 configured=1']:raise ValueError('configuration/code guard')
        binds=[fields(x)for x in lines if x.startswith('TIMELINE_BIND')]
        if len(binds)!=5 or {x.get('target')for x in binds}!=set(TARGETS) or any(set(x)!={'target','dispatcher_hook','distinct_original'}or x['dispatcher_hook']!=1 or x['distinct_original']!=1 for x in binds):raise ValueError('binding guard')
        headers=[fields(x)for x in lines if x.startswith('TIMELINE_TRACE')]
        if len(headers)!=1:raise ValueError('unique header')
        h=headers[0];keys={'status','capacity','targets','total_capacity','reserved','calls','posts','unwound','inflight','dropped','suppressed','frozen','weak_snapshot'}
        if set(h)!=keys or (h['status'],h['capacity'],h['targets'],h['total_capacity'],h['frozen'],h['weak_snapshot'])!=('frozen',8192,5,40960,1,1):raise ValueError('header contract')
        targets={};entries={};pending=set();seq=set();events={}
        for line in lines:
            if not line.startswith('TIMELINE_'):continue
            if line.startswith(('TIMELINE_BIND ','TIMELINE_TRACE ')):continue
            if not line.startswith(('TIMELINE_TARGET ','TIMELINE_ENTRY ','TIMELINE_PENDING ')):raise ValueError('unknown/malformed frame')
            row=fields(line);kind=line.split()[0]
            if kind=='TIMELINE_TARGET':
                if set(row)!={'kind','target','reserved','pre','post','unwound','inflight','dropped','suppressed','frozen'}or row['kind']>=5 or row['target']!=TARGETS[row['kind']]or row['kind']in targets or row['frozen']!=1:raise ValueError('target contract')
                targets[row['kind']]=row;continue
            slot=row['slot']
            if slot>=40960 or slot in entries or slot in pending:raise ValueError('slot duplicate/range')
            if kind=='TIMELINE_PENDING':
                if set(row)!={'slot'}:raise ValueError('pending contract')
                pending.add(slot);continue
            expected={'slot','seq','call','parent','depth','target','phase','thread','context','lr','sp','tick_ms','result'}|{f'r{i}'for i in range(3,11)}
            if set(row)!=expected or row['target']!=TARGETS[slot//8192]or row['phase']not in {'pre','post'}or not row['call']or not row['seq']or not row['depth']or row['seq']in seq:raise ValueError('entry contract')
            if bool(row['parent'])!=(row['depth']>1)or row['parent']>=row['call']or row['thread']>0xFFFFFFFF:raise ValueError('nesting/width')
            token=(row['call'],row['phase'])
            if token in events:raise ValueError('duplicate call phase')
            seq.add(row['seq']);events[token]=row;entries[slot]=row
        if set(targets)!=set(range(5)):raise ValueError('missing target')
        for i,t in targets.items():
            expected=set(range(i*8192,i*8192+min(t['reserved'],8192)))
            if (set(entries)|pending)&set(range(i*8192,(i+1)*8192))!=expected:raise ValueError('truncated slots')
            if t['dropped']!=max(0,t['reserved']-8192):raise ValueError('drop accounting')
        completed=[];incomplete=[]
        for call in sorted({k[0]for k in events}):
            pre=events.get((call,'pre'));post=events.get((call,'post'))
            if not pre or not post:incomplete.append(dict(call=call,pre=pre,post=post));continue
            if any(pre[k]!=post[k]for k in ['target','parent','depth','thread','context']+[f'r{i}'for i in range(3,11)])or pre['seq']>=post['seq']or pre['tick_ms']>post['tick_ms']:raise ValueError('pair identity/time')
            completed.append(dict(call=call,pre=pre,post=post,duration_ms=post['tick_ms']-pre['tick_ms']))
        storage_complete=not pending and not any(x['dropped']for x in targets.values())
        for row in entries.values():
            if row['phase']=='post' and (row['call'],'pre')not in events and storage_complete:raise ValueError('post without pre')
            if not row['parent']:continue
            parent=events.get((row['parent'],'pre'));parent_end=events.get((row['parent'],'post'))
            if not parent:
                if storage_complete:raise ValueError('missing parent')
                continue
            if row['thread']!=parent['thread']or row['depth']!=parent['depth']+1 or row['seq']<=parent['seq']or row['tick_ms']<parent['tick_ms']:raise ValueError('parent thread/depth/start')
            if parent_end and (row['seq']>=parent_end['seq']or row['tick_ms']>parent_end['tick_ms']):raise ValueError('child after parent end')
        completed.sort(key=lambda x:x['pre']['seq'])
        intervals=[]
        for target in TARGETS:
            calls=[x for x in completed if x['pre']['target']==target];values=[x['duration_ms']for x in calls]
            intervals.append(dict(target=target,completed=len(values),minimum_ms=min(values)if values else None,median_ms=median(values)if values else None,maximum_ms=max(values)if values else None,total_ms=sum(values)))
        result.update(status='observed',capture_verified=True,header=h,targets=[targets[i]for i in range(5)],entries=sorted(entries.values(),key=lambda x:x['seq']),pending=sorted(pending),completed_calls=completed,incomplete_calls=incomplete,intervals=intervals,storage_complete=not pending and not any(x['dropped']for x in targets.values()),purevirtual_entries=sum(x['target']==0x8286E618 and x['phase']=='pre'for x in entries.values()))
    except (ValueError,KeyError,TypeError)as exc:result['errors'].append(str(exc))
    return result

def read_frame_timelines(run_text,output,requested=False):
    result=parse_frame_timeline(run_text,requested);captures=[];errors=[];seen=set()
    for line in run_text.splitlines():
        if not line.startswith('FRAME_TIMELINE_FILE'):continue
        match=re.fullmatch(r'FRAME_TIMELINE_FILE reason=(\w+) path=(frame-timeline-\d+\.txt) success=([01])',line)
        if not match:errors.append('malformed file declaration');continue
        reason,name,success=match.groups();path=Path(output)/name
        if name in seen:errors.append('duplicate file');continue
        seen.add(name)
        if success!='1' or not path.is_file():errors.append('failed/missing file');continue
        try:raw=path.read_bytes()
        except OSError:errors.append('file read failed');continue
        parsed=parse_frame_timeline(run_text+'\n'+raw.decode('utf-8',errors='replace'),requested);parsed.update(reason=reason,path=str(path),sha256=hashlib.sha256(raw).hexdigest());captures.append(parsed)
        if not parsed['capture_verified']:errors.extend(parsed['errors']or['unexpected disabled dump'])
    if requested and not captures:errors.append('no captured file provenance')
    if captures:result=dict(captures[-1])
    if errors:result.update(status='invalid_capture',capture_verified=False,errors=errors)
    return result,captures
