"""Parse bounded host import observations without claiming object lifetimes."""
from __future__ import annotations
import re

APIS={'__imp__NtCreateEvent','__imp__NtSetEvent','__imp__NtClearEvent','__imp__NtWaitForSingleObjectEx'}
HEX_FIELDS={'context','lr','sp','result','out_handle',*(f'r{i}' for i in range(3,11))}
DEC_FIELDS={'slot','call','thread','out_read'}

def fields(text):
    return dict(re.findall(r'(\w+)=([^\s]+)',text))


def parse_event_trace(text, resolver=None):
    lines=text.splitlines();starts=[i for i,line in enumerate(lines) if line.startswith('EVENT_TRACE ')]
    result={'installed':'TITLE_EVENT_TRACE installed=1' in lines,'restored':'TITLE_EVENT_TRACE restored=1' in lines,
            'entries':[],'frames':[],'pending_slots':[],'errors':[],'capture_verified':False,
            'limits':'Four host IAT imports only; cached function pointers, SDK-internal calls and close/reuse are not covered. A pending pre is not a deadlock proof.'}
    if not starts:return result
    raw=fields(lines[starts[-1]]);result['summary']=raw
    try:
        capacity=int(raw['capacity']);reserved=int(raw['reserved']);cutoff=int(raw['cutoff'])
        dropped=int(raw['dropped']);frozen=int(raw['frozen'])
        if capacity!=8192 or reserved<0 or cutoff!=min(reserved,capacity) or dropped<0:raise ValueError('invalid ring bounds')
        block=lines[starts[-1]+1:];modules=[fields(x) for x in block if x.startswith('EVENT_TRACE_MODULE ')]
        if len(modules)!=1:raise ValueError('missing or duplicate module')
        base=int(modules[0]['base'],16);size=int(modules[0]['size'],16)
        if base<=0 or size<=0:raise ValueError('invalid module extent')
        result['module']={'base':base,'size':size}
        slots=set();phases=set()
        for line in block:
            if line.startswith('EVENT_TRACE_ENTRY '):
                row=fields(line)
                if not HEX_FIELDS|DEC_FIELDS|{'phase','api'}<=row.keys():raise ValueError('incomplete entry')
                row={k:int(v,16) if k in HEX_FIELDS else int(v) if k in DEC_FIELDS else v for k,v in row.items()}
                if row['api'] not in APIS or row['phase'] not in ('pre','post'):raise ValueError('unknown API or phase')
                if not 0<=row['slot']<cutoff or row['slot'] in slots:raise ValueError('invalid or duplicate slot')
                key=(row['call'],row['phase'])
                if key in phases:raise ValueError('duplicate call phase')
                if row['out_read'] not in (0,1):raise ValueError('invalid out-read flag')
                if row['out_read'] and not(row['api']=='__imp__NtCreateEvent' and row['phase']=='post' and row['result']&0xFFFFFFFF==0):raise ValueError('unsupported output-handle claim')
                slots.add(row['slot']);phases.add(key);result['entries'].append(row)
            elif line.startswith('EVENT_TRACE_PENDING '):
                slot=int(fields(line)['slot'])
                if not 0<=slot<cutoff or slot in slots:raise ValueError('invalid pending slot')
                slots.add(slot);result['pending_slots'].append(slot)
            elif line.startswith('EVENT_TRACE_FRAME '):
                row=fields(line);item={'slot':int(row['slot']),'index':int(row['index']),'address':int(row['address'],16),'module':row['module']}
                if not 0<=item['index']<16 or not 0<=item['slot']<cutoff:raise ValueError('invalid frame bounds')
                if row['module']=='own':
                    item['rva']=int(row['rva'],16)
                    if not 0<=item['rva']<size or item['address']!=base+item['rva']:raise ValueError('frame/module identity mismatch')
                    if resolver:item['nearest_symbol']=resolver(item['rva'])
                elif row['module']!='other':raise ValueError('unknown frame module')
                result['frames'].append(item)
        if len(slots)!=cutoff:raise ValueError('ring coverage mismatch')
        ready={x['slot'] for x in result['entries']};frame_keys=set()
        for frame in result['frames']:
            key=(frame['slot'],frame['index'])
            if frame['slot'] not in ready or key in frame_keys:raise ValueError('unbound or duplicate frame')
            frame_keys.add(key)
        pairs={}
        for row in result['entries']:pairs.setdefault(row['call'],{})[row['phase']]=row
        for pair in pairs.values():
            if 'post' in pair and 'pre' not in pair:raise ValueError('post without captured pre')
            if len(pair)==2 and any(pair['pre'][k]!=pair['post'][k] for k in ('api','thread','context',*(f'r{i}' for i in range(3,11)))):raise ValueError('call identity mismatch')
        main=[fields(x) for x in lines if x.startswith('TITLE_MAIN_THREAD ')]
        if len(main)!=1:raise ValueError('main-thread identity missing or ambiguous')
        result['main_thread']={'host':int(main[0]['host']),'context':int(main[0]['context'],16),'guest':int(main[0]['guest'])}
        result['captured_calls']=len(pairs);result['calls_without_post']=[k for k,p in pairs.items() if 'post' not in p]
        result['capture_verified']=bool(result['installed'] and result['restored'] and raw['status']=='restored' and raw.get('reset_export')=='absent' and raw.get('weak_snapshot')=='1' and frozen==1 and dropped==0 and not result['pending_slots'])
    except (KeyError,ValueError,OverflowError) as error:result['errors'].append(str(error))
    return result


def correlate_handle(trace, handle):
    """Numeric-handle correlation only, not a lifetime or complete producer graph."""
    rows=trace['entries']
    return {'handle':handle,
            'create_candidates':[x for x in rows if x['api']=='__imp__NtCreateEvent' and x['phase']=='post' and x['out_read']==1 and x['out_handle']==handle],
            'wait_pre':[x for x in rows if x['api']=='__imp__NtWaitForSingleObjectEx' and x['phase']=='pre' and x['r3']&0xFFFFFFFF==handle],
            'set_pre':[x for x in rows if x['api']=='__imp__NtSetEvent' and x['phase']=='pre' and x['r3']&0xFFFFFFFF==handle],
            'clear_pre':[x for x in rows if x['api']=='__imp__NtClearEvent' and x['phase']=='pre' and x['r3']&0xFFFFFFFF==handle],
            'limits':'Same numeric handle within this run; close/reuse and non-IAT producers are not excluded. No signal state or backend mode is inferred.'}
