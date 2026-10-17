"""Framed RAW-body lifecycle observations; never atomic/CAS or complete-writer proof."""
from __future__ import annotations
import re
TARGETS=(0x82399650,0x82399738,0x822D0A68)
HEX={'target','counter','value','context','lr','sp','result','flags'}|{f'r{i}'for i in range(3,11)}|{f'x{i}'for i in range(20)}
def fields(line):
 out={}
 for token in line.split()[1:]:
  k,sep,v=token.partition('=')
  if not sep or not v or k in out:raise ValueError('malformed or duplicate field')
  if k in HEX:
   if not re.fullmatch('[0-9a-fA-F]{1,16}',v):raise ValueError('invalid hex')
   v=int(v,16)
  elif k not in ('status','phase'):
   if not re.fullmatch('[0-9]{1,20}',v):raise ValueError('invalid decimal')
   v=int(v)
   if v>=2**64:raise ValueError('overflow')
  out[k]=v
 return out

def parse_counter_trace(text,requested=False):
 result=dict(status='disabled'if not requested else'invalid_capture',capture_verified=False,errors=[],targets=[],entries=[],pending=[],increments=[],callbacks=[],reservations=[],storage_complete=False,complete_lifecycle_verified=False,scope='Read-only non-atomic pre/post snapshots and actual generated-body calls; no CAS linearization/all-writer or game-boot proof.')
 if not requested:return result
 try:
  lines=text.splitlines()
  if [x for x in lines if x.startswith('TITLE_WAIT_SDK ')]!=['TITLE_WAIT_SDK parent_attested=1']:raise ValueError('SDK attestation')
  if [x for x in lines if x.startswith('TITLE_COUNTER_TRACE ')]!=['TITLE_COUNTER_TRACE enabled=1 code_guard=1 binding_guard=1 configured=1']:raise ValueError('configuration/body/binding guard')
  binds=[fields(x)for x in lines if x.startswith('COUNTER_BIND ')]
  if len(binds)!=3 or {x['target']for x in binds}!=set(TARGETS) or any(set(x)!={'target','dispatcher_hook','distinct_original'}or x['dispatcher_hook']!=1 or x['distinct_original']!=1 for x in binds):raise ValueError('distinct original/dispatcher binding')
  initial=[fields(x)for x in lines if x.startswith('COUNTER_INITIAL ')]
  if len(initial)!=1 or set(initial[0])!={'counter','word_known','value'}or initial[0]['counter']!=0x83265218 or initial[0]['word_known']!=1 or initial[0]['value']>0xFFFFFFFF:raise ValueError('initial counter unavailable')
  result['initial_counter']=initial[0]['value']
  heads=[fields(x)for x in lines if x.startswith('COUNTER_TRACE ')]
  if len(heads)!=1:raise ValueError('unique header required')
  h=heads[0];result['counters']=h
  if set(h)!={'status','capacity','targets','total_capacity','reserved','calls','posts','dropped','suppressed','frozen','weak_snapshot'}or (h['status'],h['capacity'],h['targets'],h['total_capacity'],h['frozen'],h['weak_snapshot'])!=('frozen',8192,3,24576,1,1):raise ValueError('header contract')
  targets={};entries={};pending={};seqs=set();calls={}
  for line in lines:
   if not line.startswith(('COUNTER_TARGET','COUNTER_ENTRY','COUNTER_PENDING')):continue
   row=fields(line);kind=line.split()[0]
   if kind=='COUNTER_TARGET':
    expected={'kind','target','reserved','pre','post','selected','selected_post','unknown','unknown_post','dropped','suppressed','frozen'}
    if set(row)!=expected or row['kind']>=3 or row['target']!=TARGETS[row['kind']] or row['kind']in targets or row['frozen']!=1:raise ValueError('target contract')
    targets[row['kind']]=row
   elif kind in ('COUNTER_ENTRY','COUNTER_PENDING'):
    slot=row['slot']
    if slot>=24576 or slot in entries or slot in pending:raise ValueError('duplicate/out-of-range slot')
    if kind=='COUNTER_PENDING':
     if set(row)!={'slot'}:raise ValueError('pending contract')
     pending[slot]=row;continue
    expected={'slot','seq','call','parent','target','phase','thread','context','lr','sp','result','selection','flags'}|{f'r{i}'for i in range(3,11)}|{f'x{i}'for i in range(20)}
    if set(row)!=expected or row['target']!=TARGETS[slot//8192] or row['phase']not in ('pre','post')or not row['call']or not row['seq']or row['seq']in seqs or row['selection']not in (1,2)or row['flags']&~0xFFFFF:raise ValueError('entry/selection/flags contract')
    if row['phase']=='pre'and row['selection']!=1:raise ValueError('unselected pre')
    if row['x1']>0xFFFFFFFF and row['flags']&2:raise ValueError('counter width')
    token=(row['call'],row['phase'])
    if token in calls:raise ValueError('duplicate call phase')
    calls[token]=row;seqs.add(row['seq']);entries[slot]=row
   else:raise ValueError('unknown record')
  if set(targets)!={0,1,2}:raise ValueError('all target counters required')
  for k,t in targets.items():
   expected=set(range(k*8192,k*8192+min(t['reserved'],8192)))
   if expected!={x for x in entries.keys()|pending.keys()if x//8192==k}:raise ValueError('reserved record truncated')
  for call in {x[0]for x in calls}:
   pre=calls.get((call,'pre'));post=calls.get((call,'post'))
   if pre and post:
    stable=['parent','target','thread','context']+[f'r{i}'for i in range(3,11)]
    if any(pre[x]!=post[x]for x in stable)or pre['seq']>=post['seq']:raise ValueError('call pair mismatch')
   witness=pre or post;t=targets[TARGETS.index(witness['target'])]
   cut=bool(t['dropped']or t['suppressed']or any(slot//8192==t['kind']for slot in pending))
   if not pre and not cut:raise ValueError('orphan post without cut evidence')
   if not post and not cut and t['selected']<=t['selected_post']:raise ValueError('missing post without inflight/cut evidence')
   # Missing mate may be an inflight, suppressed, or capacity-cut record.
   if not pre:continue
   value=lambda row,slot:row[f'x{slot}']if row and row['selection']==1 and row['flags']&(1<<slot)else None
   if value(pre,0)!=0x83265218:continue
   item=dict(call=call,parent=pre['parent'],thread=pre['thread'],lr=pre['lr'],before=value(pre,1),after=value(post,1),original_args=[pre[f'r{i}']for i in range(3,11)],post_return=post['result']if post else None,pre=pre,post=post)
   if pre['target']==TARGETS[0]and pre['r3']&0xFFFFFFFF==0x83265218:result['increments'].append(item)
   elif pre['target']==TARGETS[1]and value(pre,8)==0x83265218:result['callbacks'].append(item)
   elif pre['target']==TARGETS[2]and pre['lr']==0x8239969C and pre['parent']:result['reservations'].append(item)
  for name in ('increments','callbacks','reservations'):result[name].sort(key=lambda x:x['pre']['seq'])
  result.update(status='captured',capture_verified=True,targets=list(targets.values()),entries=list(entries.values()),pending=list(pending.values()),storage_complete=not pending and not h['dropped']and not h['suppressed']and not any(x['unknown']or x['unknown_post']for x in targets.values()))
 except (KeyError,ValueError,TypeError)as error:
  result['errors'].append(str(error));result['increments']=[];result['callbacks']=[];result['reservations']=[]
 return result
