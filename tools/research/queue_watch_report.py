"""Validate bounded, non-atomic queue prefixes; never infer executed callbacks."""
import re

def parse_queue_watch(text, requested=False):
    result=dict(status='disabled' if not requested else 'invalid_capture',capture_verified=False,errors=[],entries=[],pending=[],executed_callback_proof=False,scope='Non-atomic queue/head prefixes only; pointer changes are not instruction or all-writer proof.')
    if not requested:return result
    try:
        def fields(line):
            out={}
            for token in line.split()[1:]:
                k,sep,v=token.partition('=')
                if not sep or k in out:raise ValueError('malformed/duplicate field')
                if k in {'status','head_status','table_status','head_hex','table_hex'}:out[k]=v;continue
                base=16 if k in {'flags','counter','global','manager'} or re.fullmatch(r'x\d+',k) else 10
                if not re.fullmatch('[0-9A-Fa-f]{1,16}' if base==16 else '[0-9]{1,20}',v):raise ValueError('invalid number')
                out[k]=int(v,base)
                if out[k]>=2**64:raise ValueError('overflow')
            return out
        lines=text.splitlines()
        if [x for x in lines if x.startswith('TITLE_COUNTER_TRACE')]!=['TITLE_COUNTER_TRACE enabled=1 code_guard=1 binding_guard=1 configured=1']:raise ValueError('code guard/configuration')
        if [x for x in lines if x.startswith('TITLE_WAIT_SDK')]!=['TITLE_WAIT_SDK parent_attested=1']:raise ValueError('SDK attestation')
        for line in lines:
            if line.startswith('QUEUE_WATCH_') and not line.startswith(('QUEUE_WATCH_TRACE','QUEUE_WATCH_ENTRY','QUEUE_WATCH_PENDING','QUEUE_WATCH_FILE')):raise ValueError('unknown queue namespace')
            if line.startswith(('QUEUE_WATCH_TRACE','QUEUE_WATCH_ENTRY','QUEUE_WATCH_PENDING')) and not line.startswith(('QUEUE_WATCH_TRACE ','QUEUE_WATCH_ENTRY ','QUEUE_WATCH_PENDING ')):raise ValueError('malformed frame')
        heads=[fields(x) for x in lines if x.startswith('QUEUE_WATCH_TRACE ')]
        if len(heads)!=1:raise ValueError('unique header')
        h=heads[0]
        if set(h)!={'status','capacity','reserved','dropped','frozen','weak_snapshot','counter','global','manager'} or (h['status'],h['capacity'],h['frozen'],h['weak_snapshot'],h['counter'],h['global'],h['manager'])!=('frozen',128,1,1,0x83265218,0x83263ACC,0x83276B18):raise ValueError('header contract')
        entries={};pending=set()
        for line in lines:
            if not line.startswith(('QUEUE_WATCH_ENTRY ','QUEUE_WATCH_PENDING ')):continue
            row=fields(line);slot=row['slot']
            if slot>=min(h['reserved'],128) or slot in entries or slot in pending:raise ValueError('duplicate/out-of-range slot')
            if line.startswith('QUEUE_WATCH_PENDING '):
                if set(row)!={'slot'}:raise ValueError('pending contract')
                pending.add(slot);continue
            expected={'slot','tick_ms','status','flags','head_captured','head_status','head_hex','table_captured','table_status','table_hex'}|{f'x{i}' for i in range(20)}
            if set(row)!=expected or row['flags']&~0xFFFFF:raise ValueError('entry contract')
            if row['status'] not in {'fixed-unreadable','empty','bounds-invalid','head-unreadable','head-only','captured'}:raise ValueError('status contract')
            failures={'invalid-view','null-guest','invalid-count','guest-overflow','outside-span','host-overflow','query-failed','unreadable','partial-read','read-failed'}
            if row['status'] in {'fixed-unreadable','empty','bounds-invalid'} and (row['head_status'],row['table_status'])!=('not-read','not-read'):raise ValueError('unread status')
            if row['status']=='head-unreadable' and (row['head_status'] not in failures or row['table_status']!='not-read'):raise ValueError('head failure status')
            if row['status']=='head-only' and (row['head_status']!='ok' or row['table_status'] not in failures|{'outside-image'}):raise ValueError('table failure status')
            if row['status']=='captured' and (row['head_status'],row['table_status'])!=('ok','ok'):raise ValueError('captured status')
            for name,size in [('head',32),('table',12)]:
                n=row[name+'_captured'];raw=row[name+'_hex']
                if n>size or len(raw)!=2*n or (raw and not re.fullmatch('[0-9A-Fa-f]+',raw)):raise ValueError('prefix length/encoding')
                if n and row[name+'_status']!='ok':raise ValueError('prefix status')
            for i in range(20):
                if row[f'x{i}']>0xFFFFFFFF or (not row['flags']&(1<<i) and row[f'x{i}']):raise ValueError('word width/unflagged value')
            expected_prefix_flags=0
            if row['head_captured']:
                if row['head_captured']<4:raise ValueError('short head')
                expected_prefix_flags|=1<<9
                for i in range(1,row['head_captured']//4):expected_prefix_flags|=1<<(12+i)
            if row['table_captured']:expected_prefix_flags|=7<<10
            if row['flags']&~0x1FF!=expected_prefix_flags:raise ValueError('prefix flags')
            if row['status'] in {'fixed-unreadable','empty','bounds-invalid','head-unreadable'} and (row['head_captured'] or row['table_captured']):raise ValueError('status prefix disagreement')
            if row['status']=='head-only' and (row['head_captured']<4 or row['table_captured']):raise ValueError('head-only contract')
            critical=(1<<2)|(1<<3)|(1<<4)|(1<<7)
            fixed=row['flags']&critical==critical
            begin,end,write,headptr=(row[f'x{i}'] for i in (2,3,4,7))
            count=min(32,end-headptr) if end>=headptr else 0
            bounds=begin<=headptr<end and begin<=write<=end and count>=4 and ((0x10000<=headptr and headptr+count<=0x7F000000) or (0x82000000<=headptr and headptr+count<=0x83330000))
            if row['status']=='fixed-unreadable' and fixed:raise ValueError('fixed status')
            if row['status']!='fixed-unreadable' and not fixed:raise ValueError('fixed fields missing')
            if row['status']=='empty' and headptr!=write:raise ValueError('empty predicate')
            if row['status'] not in {'fixed-unreadable','empty'} and headptr==write:raise ValueError('nonempty predicate')
            if row['status']=='bounds-invalid' and bounds:raise ValueError('bounds status')
            if row['status'] in {'head-unreadable','head-only','captured'} and not bounds:raise ValueError('head bounds')
            if row['status'] in {'head-only','captured'} and row['head_captured']!=count:raise ValueError('head bound length')
            head=bytes.fromhex(row['head_hex']);table=bytes.fromhex(row['table_hex'])
            for i in range(len(head)//4):
                slotfield=9 if i==0 else 12+i
                if not row['flags']&(1<<slotfield) or row[f'x{slotfield}']!=int.from_bytes(head[4*i:4*i+4],'big'):raise ValueError('head word disagreement')
            if row['status']=='head-only' and (row['table_status']=='outside-image')==(0x82000000<=row['x9']<=0x83330000-12):raise ValueError('table failure range')
            if table:
                if len(table)!=12 or len(head)<4 or not 0x82000000<=row['x9']<=0x83330000-12:raise ValueError('table bounds')
                for i in range(3):
                    if not row['flags']&(1<<(10+i)) or row[f'x{10+i}']!=int.from_bytes(table[4*i:4*i+4],'big'):raise ValueError('table word disagreement')
            if row['status']=='captured' and (len(table)!=12 or len(head)<4):raise ValueError('captured incomplete')
            entries[slot]=row
        if set(entries)|pending!=set(range(min(h['reserved'],128))):raise ValueError('truncated slots')
        if h['dropped']!=max(0,h['reserved']-128):raise ValueError('drop accounting')
        rows=[entries[k] for k in sorted(entries)]
        if any(a['tick_ms']>b['tick_ms'] for a,b in zip(rows,rows[1:])):raise ValueError('time order')
        result.update(status='observed',capture_verified=True,header=h,entries=rows,pending=sorted(pending),storage_complete=not pending and not h['dropped'])
    except (ValueError,KeyError,TypeError) as exc:result['errors'].append(str(exc))
    return result

def read_queue_watches(run_text, output, requested=False):
    """Reject every bad declared file, including failure after an earlier good dump."""
    import hashlib
    from pathlib import Path
    result=parse_queue_watch(run_text,requested);captures=[];errors=[]
    declarations=[x for x in run_text.splitlines() if x.startswith('QUEUE_WATCH_FILE')]
    seen=set()
    for line in declarations:
        match=re.fullmatch(r'QUEUE_WATCH_FILE reason=(\w+) path=(queue-watch-\d+\.txt) success=([01])',line)
        if not match:errors.append('malformed file declaration');continue
        reason,name,success=match.groups();path=Path(output)/name
        if name in seen:errors.append('duplicate declared file');continue
        seen.add(name)
        if success!='1' or not path.is_file():errors.append('failed/missing declared file');continue
        try:raw=path.read_bytes()
        except OSError:errors.append('declared file read failed');continue
        parsed=parse_queue_watch(run_text+'\n'+raw.decode('utf-8',errors='replace'),requested)
        parsed.update(reason=reason,path=str(path),sha256=hashlib.sha256(raw).hexdigest());captures.append(parsed)
        if not parsed['capture_verified']:errors.extend(parsed['errors'] or ['unexpected dump while disabled'])
    if captures:result=dict(captures[-1])
    if errors:result.update(status='invalid_capture',capture_verified=False,errors=errors)
    return result,captures
