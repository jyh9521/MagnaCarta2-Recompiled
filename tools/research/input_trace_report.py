"""Bounded original input return/consumer snapshots, never physical-input proof."""
import hashlib,re
from pathlib import Path
FAIL={'invalid-view','null-guest','invalid-count','guest-overflow','outside-span','host-overflow','query-failed','unreadable','partial-read','read-failed'}
HEX={'context','lr','sp','user','state_address','obj','key','opaque','new_value','old_word','result'}
def fields(line,strings=(),hexextra=()):
    row={}
    for item in line.split()[1:]:
        k,sep,v=item.partition('=')
        if not sep or not v or k in row:raise ValueError('malformed/duplicate field')
        if k in strings:row[k]=v;continue
        base=16 if k in HEX or k in hexextra else 10
        if not re.fullmatch('[0-9A-Fa-f]{1,16}'if base==16 else'[0-9]{1,20}',v)or int(v,base)>=2**64:raise ValueError('numeric width')
        row[k]=int(v,base)
    return row

def parse_input_trace(text,kind='INPUT_STATE',requested=False):
    result=dict(status='disabled'if not requested else'invalid_capture',capture_verified=False,errors=[],entries=[],pending=[],transitions=[],storage_complete=False,coverage_complete=False,physical_input_verified=False,event_callback_verified=False)
    if not requested:return result
    try:
        if kind not in {'INPUT_STATE','START_EVENT','CONFIRM_EVENT'}:raise ValueError('trace kind')
        start=kind!='INPUT_STATE';confirm=kind=='CONFIRM_EVENT';key=10 if confirm else 5;caller=0x827B4DEC if confirm else 0x827B4D10;capacity=16384 if start else 8192;lines=text.splitlines()
        if [x for x in lines if x.startswith('TITLE_WAIT_SDK')]!=['TITLE_WAIT_SDK parent_attested=1']:raise ValueError('SDK attestation')
        if [x for x in lines if x.startswith('TITLE_INPUT_TRACE')]!=['TITLE_INPUT_TRACE enabled=1 code_guard=1 binding_guard=1 configured=1']:raise ValueError('code/configuration guard')
        binds=[fields(x,hexextra={'target'})for x in lines if x.startswith('INPUT_BIND')]
        if len(binds)!=2 or {x.get('target')for x in binds}!={0x82868178,0x827B4938}or any(set(x)!={'target','dispatcher_hook','distinct_original'}or x['dispatcher_hook']!=1 or x['distinct_original']!=1 for x in binds):raise ValueError('actual original binding')
        headers=[fields(x,{'status'})for x in lines if x.startswith(kind+'_TRACE')]
        if len(headers)!=1:raise ValueError('unique header')
        h=headers[0];keys={'status','capacity','reserved','calls','posts','dropped','suppressed','frozen','weak_snapshot'}
        if start:keys|={'selected','selected_posts','invalid_user','unknown','unwound','inflight'}
        if set(h)!=keys or(h['status'],h['capacity'],h['frozen'],h['weak_snapshot'])!=('frozen',capacity,1,1):raise ValueError('header contract')
        rows={};pending=set();seq=set();events={}
        for line in lines:
            if not line.startswith(kind+'_'):continue
            if line.startswith((kind+'_TRACE ',kind+'_FILE ')):continue
            if not line.startswith((kind+'_ENTRY ',kind+'_PENDING ')):raise ValueError('unknown/malformed frame')
            x=fields(line,{'phase','read_status','hex','old_status'},set()if start else{'status'});slot=x['slot']
            if slot>=min(h['reserved'],capacity)or slot in rows or slot in pending:raise ValueError('slot range/duplicate')
            if line.startswith(kind+'_PENDING '):
                if set(x)!={'slot'}:raise ValueError('pending contract')
                pending.add(slot);continue
            expected={'slot','seq','call','thread','context','lr','sp','user','tick_ms'}
            expected|={'phase','obj','key','opaque','new_value','old_known','old_word','old_status','result'}if start else{'state_address','status','captured','read_status','hex'}
            if set(x)!=expected or not x['seq']or not x['call']or x['call']>h['calls']or x['seq']>min(h['reserved'],capacity)or x['seq']in seq or x['thread']>0xFFFFFFFF:raise ValueError('entry contract')
            if start:
                address=(x['obj']&0xFFFFFFFF)+(0x4C0 if confirm else 0x4AC)+x['user']*0xC0
                ordinary=0x10000<=address<=0x7F000000-4
                if x['old_known'] and not ordinary:raise ValueError('oldword address')
                if not x['old_known']:
                    expected_status='address-overflow'if address>0xFFFFFFFC else'outside-ram'if not ordinary else None
                    if expected_status and x['old_status']!=expected_status or not expected_status and x['old_status']in {'address-overflow','outside-ram'}:raise ValueError('oldword failure address')
                if x['phase']not in {'pre','post'}or x['user']>3 or x['key']&0xFFFFFFFF!=key or x['old_known']not in(0,1)or x['old_word']>0xFFFFFFFF:raise ValueError('START filter/word')
                if x['phase']=='pre'and x['lr']!=caller:raise ValueError('original caller')
                if x['old_known']and x['old_status']!='ok' or not x['old_known']and(x['old_word']or x['old_status']not in FAIL|{'outside-ram','address-overflow'}):raise ValueError('oldword validity')
                token=(x['call'],x['phase'])
            else:
                if x['captured']not in(0,16):raise ValueError('state size')
                if x['captured']==16:
                    if x['status']!=0 or x['read_status']!='ok'or not re.fullmatch('[0-9A-Fa-f]{32}',x['hex'])or not 0x10000<=x['state_address']<=0x7F000000-16:raise ValueError('successful state contract')
                    raw=bytes.fromhex(x['hex']);x.update(packet_number=int.from_bytes(raw[:4],'big'),buttons=int.from_bytes(raw[4:6],'big'),start_pressed=bool(raw[5]&0x10),confirm_pressed=bool(raw[4]&0x10))
                elif x['hex']!='-'or(x['status']!=0 and x['read_status']!='not-read-status')or(x['status']==0 and x['read_status']not in FAIL|{'outside-ordinary-ram'}):raise ValueError('unknown state contract')
                token=x['call']
            if token in events:raise ValueError('duplicate call phase')
            events[token]=x;seq.add(x['seq']);rows[slot]=x
        if set(rows)|pending!=set(range(min(h['reserved'],capacity))):raise ValueError('truncated slots')
        expected_drop=max(0,h['reserved']-capacity)
        if h['dropped']>expected_drop or h['reserved']>h['calls']+h['posts'] or not start and h['reserved']>min(h['calls'],h['posts']):raise ValueError('counter/drop accounting')
        if start and (h['reserved']>2*h['calls']or h['reserved']>h['selected']+h['selected_posts']or sum(x['phase']=='pre'for x in rows.values())>h['selected']or sum(x['phase']=='post'for x in rows.values())>min(h['posts'],h['selected_posts'])):raise ValueError('selected counter accounting')
        ordered=sorted(rows.values(),key=lambda x:x['seq']);transitions=[];incomplete=[]
        if start:
            for call in sorted({k[0]for k in events}):
                pre,post=events.get((call,'pre')),events.get((call,'post'))
                if not pre or not post:incomplete.append(dict(call=call,pre=pre,post=post));continue
                if any(pre[k]!=post[k]for k in ['thread','context','obj','key','user','opaque','new_value'])or pre['seq']>=post['seq']or pre['tick_ms']>post['tick_ms']:raise ValueError('consumer pair identity/time')
                if pre['old_known']and post['old_known']and pre['old_word']!=post['old_word']:transitions.append(dict(call=call,pre=pre,post=post))
            result['incomplete_calls']=incomplete
        result.update(status='observed',capture_verified=True,header=h,entries=ordered,pending=sorted(pending),transitions=transitions,storage_complete=not pending and not expected_drop and not h['suppressed'] and(not start or not incomplete),file_storage_complete=not pending and not expected_drop,drop_accounting_pending=expected_drop-h['dropped'])
    except(ValueError,KeyError,TypeError)as exc:result['errors'].append(str(exc))
    return result

def read_input_traces(run_text,output,requested=False,confirm_requested=False):
    results={}
    for kind,marker,stem in [('INPUT_STATE','INPUT_STATE_FILE','input-state'),('START_EVENT','START_EVENT_FILE','start-event'),('CONFIRM_EVENT','CONFIRM_EVENT_FILE','confirm-event')]:
        enabled=confirm_requested if kind=='CONFIRM_EVENT'else requested
        result=parse_input_trace(run_text,kind,enabled);captures=[];errors=[];seen=set()
        for line in run_text.splitlines():
            if not line.startswith(marker):continue
            match=re.fullmatch(marker+r' reason=(\w+) path=('+stem+r'-\d+\.txt) success=([01])',line)
            if not match:errors.append('malformed file declaration');continue
            reason,name,success=match.groups();path=Path(output)/name
            if name in seen:errors.append('duplicate file');continue
            seen.add(name)
            if success!='1'or not path.is_file():errors.append('failed/missing file');continue
            try:raw=path.read_bytes()
            except OSError:errors.append('file read failed');continue
            parsed=parse_input_trace(run_text+'\n'+raw.decode('utf-8',errors='replace'),kind,enabled);parsed.update(reason=reason,path=str(path),sha256=hashlib.sha256(raw).hexdigest());captures.append(parsed)
            if not parsed['capture_verified']:errors.extend(parsed['errors']or['disabled capture'])
        if enabled and not captures:errors.append('no captured file provenance')
        if captures:result=dict(captures[-1])
        if errors:result.update(status='invalid_capture',capture_verified=False,errors=errors)
        results[kind.lower()]=result;results[kind.lower()+'_captures']=captures
    return results




def parse_scripted_controller(text,requested=False,confirm_requested=False,confirm_neutral=False):
    result=dict(status='disabled'if not requested else'invalid_capture',capture_verified=False,errors=[],physical_input_verified=False)
    if not requested:return result
    try:
        lines=text.splitlines()
        configs=[x for x in lines if x.startswith('TITLE_SCRIPTED_START')]
        if len(configs)!=1:raise ValueError('unique scripted configuration')
        config=fields(configs[0],{'input_source'})
        if set(config)!={'enabled','input_source','armed','sdk_guard','neutral_only'}or(config['enabled'],config['input_source'],config['armed'],config['sdk_guard'])!=(1,'synthetic',1,1)or config['neutral_only']not in (0,1):raise ValueError('scripted configuration')
        setups=[x for x in lines if x.startswith('SCRIPTED_CONTROLLER_SETUP')]
        if setups!=['SCRIPTED_CONTROLLER_SETUP status=00000000 input_source=synthetic setup_before_add=1 default_drivers_retained=1']:raise ValueError('typed driver setup')
        records=[x for x in lines if x.startswith('SCRIPTED_CONTROLLER ')];unknown=[x for x in lines if x.startswith('SCRIPTED_CONTROLLER')and x not in records+setups]
        if len(records)!=1 or unknown:raise ValueError('unique scripted record')
        x=fields(records[0],{'input_source'},{'device'});expected={'input_source','automatic_only','physical_verified','made','setup','armed','neutral_only','device','pulse_start_ms','pulse_width_ms','arm_tick','polls','pressed_polls','released_polls','packet','first_tick','last_tick','capabilities','keystroke_polls','key_down','key_up','empty','vibration','left','right','errors','setup_calls'}
        if set(x)!=expected or (x['input_source'],x['automatic_only'],x['physical_verified'],x['made'],x['setup'],x['armed'],x['device'],x['pulse_start_ms'],x['pulse_width_ms'],x['setup_calls'])!=('synthetic',1,0,1,1,1,0x5343524950540001,25000,500,1)or x['neutral_only']!=config['neutral_only']:raise ValueError('synthetic driver contract')
        cr={}
        confirms=[q for q in lines if q.startswith('SCRIPTED_CONFIRM ')]
        config_lines=[q for q in lines if q.startswith('TITLE_SCRIPTED_CONFIRM')]
        if not confirm_requested and (confirms or config_lines not in ([],['TITLE_SCRIPTED_CONFIRM enabled=0 sdk_guard=1'])):raise ValueError('unrequested confirm mode')
        if confirm_requested:
            if [q for q in lines if q.startswith('TITLE_SCRIPTED_CONFIRM')]!=['TITLE_SCRIPTED_CONFIRM enabled=1 sdk_guard=1']or len(confirms)!=1:raise ValueError('confirm configuration')
            cr=fields(confirms[0]);expected_cr={'enabled','neutral_only','confirm_neutral','confirm_start_ms','confirm_width_ms','confirm_polls','confirm_released_polls','a_key_down','a_key_up'}
            if set(cr)!=expected_cr or(cr['enabled'],cr['neutral_only'],cr['confirm_start_ms'],cr['confirm_width_ms'])!=(1,x['neutral_only'],32000,500):raise ValueError('confirm schedule contract')
            if cr['confirm_neutral']not in(0,1)or cr['confirm_neutral']!=int(confirm_neutral):raise ValueError('confirm control mode')
            if cr['confirm_neutral']and any(cr[q]for q in ['confirm_polls','confirm_released_polls','a_key_down','a_key_up']):raise ValueError('suppressed confirm')
            if cr['confirm_released_polls']>x['released_polls']or cr['a_key_down']>1 or cr['a_key_up']>cr['a_key_down']:raise ValueError('confirm counters')
            if x['neutral_only']and any(cr[q]for q in ['confirm_polls','confirm_released_polls','a_key_down','a_key_up']):raise ValueError('neutral confirm')
        a_polls=cr.get('confirm_polls',0);a_down=cr.get('a_key_down',0);a_up=cr.get('a_key_up',0)
        if x['pressed_polls']+x['released_polls']+a_polls>x['polls']or x['key_down']>1 or x['key_up']>x['key_down']or x['empty']+x['key_down']+x['key_up']+a_down+a_up!=x['keystroke_polls']or max(x['left'],x['right'])>65535 or x['packet']not in ((1,2,3,4,5)if confirm_requested else(1,2,3)):raise ValueError('driver accounting')
        if x['polls']and x['first_tick']>x['last_tick']or not x['polls']and(x['first_tick']or x['last_tick']):raise ValueError('poll clock')
        if x['neutral_only']and(x['pressed_polls']or x['released_polls']or x['key_down']or x['key_up']or x['packet']!=1):raise ValueError('neutral control')
        expected_packet=5 if cr.get('confirm_released_polls',0)else 4 if a_polls else 3 if x['released_polls']else 2 if x['pressed_polls']else 1
        if x['packet']!=expected_packet:raise ValueError('packet phase')
        if not x['vibration']and(x['left']or x['right']):raise ValueError('uncalled vibration state')
        result.update(status='observed',capture_verified=True,record=x,configuration=config,confirm_record=cr)
    except(ValueError,KeyError,TypeError)as exc:result['errors'].append(str(exc))
    return result
