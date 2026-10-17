"""Strict read-only schedule trace framing. Sparse observations never prove deadlock."""
from __future__ import annotations
import re

APIS=('__imp__KeDelayExecutionThread','__imp__RtlEnterCriticalSection','__imp__RtlLeaveCriticalSection')
HEX=set(('lr','a0','a1','a2','context','sp','result','r29','r30','r31','flags'))|{f'r{i}' for i in range(3,11)}|{f'x{i}' for i in range(8)}

def _fields(line):
 values={}
 for token in line.split()[1:]:
  name,sep,value=token.partition('=')
  if not sep or name in values or not value:raise ValueError('malformed/duplicate field')
  if name in HEX:
   if not re.fullmatch('[0-9A-Fa-f]{1,16}',value):raise ValueError('invalid hex')
   value=int(value,16)
  elif name not in ('status','api','phase'):
   if not re.fullmatch('[0-9]{1,20}',value):raise ValueError('invalid decimal')
   value=int(value)
   if value>2**64-1:raise ValueError('integer overflow')
  values[name]=value
 return values

def parse_schedule_trace(text,requested=False):
 result=dict(status='disabled' if not requested else 'invalid_capture',capture_verified=False,
   errors=[],keys=[],entries=[],pending=[],poll_samples=[],coverage_complete=False,
   deadlock_verified=False,scope='Weak counter snapshots and bounded per-key time samples; no guest state mutation or deadlock/boot proof.')
 if not requested:return result
 try:
  lines=text.splitlines()
  if [x for x in lines if x.startswith('TITLE_WAIT_SDK ')]!=['TITLE_WAIT_SDK parent_attested=1']:raise ValueError('SDK attestation missing or duplicate')
  if [x for x in lines if x.startswith('TITLE_SCHEDULE_TRACE installed=')]!=['TITLE_SCHEDULE_TRACE installed=1 code_guard=1']:raise ValueError('original code/install guard')
  if [x for x in lines if x.startswith('TITLE_SCHEDULE_TRACE restored=')]!=['TITLE_SCHEDULE_TRACE restored=1']:raise ValueError('IAT restoration not verified')
  heads=[_fields(x) for x in lines if x.startswith('SCHEDULE_TRACE ')]
  if len(heads)!=1:raise ValueError('unique trace header required')
  h=heads[0];result['counters']=h
  if h['status']!='restored' or (h['keys'],h['bins'],h['bucket_ms'],h['frozen'],h['weak_snapshot'])!=(192,128,500,1,1):raise ValueError('trace contract mismatch')
  keys={};entries={};pending={};apis={}
  for line in lines:
   if not line.startswith(('SCHEDULE_KEY','SCHEDULE_ENTRY','SCHEDULE_PENDING','SCHEDULE_API')):continue
   row=_fields(line);kind=line.split()[0]
   if kind=='SCHEDULE_API':
    if set(row)!={'api','pre','post','key_overflow'} or row['api'] not in APIS or row['api'] in apis:raise ValueError('API counter mismatch')
    apis[row['api']]=row
   elif kind=='SCHEDULE_KEY':
    if set(row)!={'key','api','thread','lr','a0','a1','a2','pre','post','sampled'}:raise ValueError('key field mismatch')
    key=row['key']
    if key in keys or key>=192 or row['api'] not in APIS or key//64!=APIS.index(row['api']):raise ValueError('key identity mismatch')
    if row['sampled']>128 or row['sampled']>row['pre']:raise ValueError('sample count contradiction')
    keys[key]=row
   elif kind in ('SCHEDULE_ENTRY','SCHEDULE_PENDING'):
    if row['phase'] not in ('pre','post') or row['bin']>=128 or row['key']>=192:raise ValueError('sample address mismatch')
    token=(row['key'],row['bin'],row['phase'])
    if token in entries or token in pending:raise ValueError('duplicate sample phase')
    if kind=='SCHEDULE_PENDING':
     if set(row)!={'key','bin','phase'}:raise ValueError('pending fields')
     pending[token]=row
    else:
     expected={'key','bin','phase','call','tick_ms','thread','context','lr','sp','result','r29','r30','r31','flags'}|{f'r{i}' for i in range(3,11)}|{f'x{i}' for i in range(8)}
     if set(row)!=expected or row['flags']&~0xFF:raise ValueError('entry fields/hook failure')
     if row['phase']=='pre' and row['tick_ms']//500!=row['bin']:raise ValueError('sample clock/bin mismatch')
     entries[token]=row
   else:raise ValueError('unknown schedule record')
  if set(apis)!=set(APIS):raise ValueError('all API counters required')
  result['api_counters']=list(apis.values())
  for token,row in entries.items():
   k=keys.get(row['key'])
   if k is None or k['thread']!=row['thread']:raise ValueError('sample missing owning key')
   if row['phase']=='pre' and (k['lr']!=row['lr'] or k['a0']!=row['r3'] or (k['api']==APIS[0] and (k['a1'],k['a2'])!=(row['r4'],row['r5']))):raise ValueError('sample/key args mismatch')
   mate=entries.get((row['key'],row['bin'],'post' if row['phase']=='pre' else 'pre'))
   if mate and (mate['call']!=row['call'] or mate['context']!=row['context'] or any(mate[f'r{i}']!=row[f'r{i}'] for i in range(3,11)) or (row['phase']=='post' and row['tick_ms']<mate['tick_ms'])):raise ValueError('pre/post pair mismatch')
   if not mate and (row['key'],row['bin'],'post' if row['phase']=='pre' else 'pre') not in pending:raise ValueError('unreported missing phase')
   if row['phase']=='pre' and k['api']==APIS[0] and row['lr']==0x82869854 and row['x1']==0x823997AC and row['flags']&0x1F==0x1F:
    counter=row['x4'];threshold=row['x3']&0xFFFFFFFF
    result['poll_samples'].append(dict(call=row['call'],tick_ms=row['tick_ms'],thread=row['thread'],pointer=row['x2']&0xFFFFFFFF,counter=counter,threshold=threshold,condition_gt=counter>threshold,interval_raw=row['x0'],alertable=row['r4']&255,global_word=row['x5'] if row['flags']&32 else None,parent_lr=row['x7'] if row['flags']&128 else None))
  for k in keys.values():
   observed_bins={t[1] for t in entries.keys()|pending.keys() if t[0]==k['key']}
   if k['sampled']>len(observed_bins):raise ValueError('claimed samples missing from trace')
  for token in pending:
   if token[0] not in keys:raise ValueError('pending key missing')
  result.update(status='captured',capture_verified=True,keys=list(keys.values()),entries=list(entries.values()),pending=list(pending.values()),sampled_records_complete=h['key_overflow']==0 and h['late']==0 and not pending,coverage_complete=False)
 except (KeyError,ValueError,TypeError) as error:
  result['errors'].append(str(error));result['poll_samples']=[]
 return result
