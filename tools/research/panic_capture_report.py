"""Strict bounded parser for the opt-in original-panic observation protocol."""
from __future__ import annotations
import re


def parse_panic_capture(text):
    result = {'requested': False, 'success': False, 'reads': {}, 'errors': [],
              'scope': 'Post-fault bounded observations, not an atomic snapshot or root-cause proof.'}
    gates = re.findall(r'^PANIC_GATE requested=1 matched=([01]) lr=([0-9A-F]{8})$', text, re.M)
    if not gates:
        return result
    result['requested'] = True
    if sum(line.startswith('PANIC_GATE ') for line in text.splitlines())!=len(gates):result['errors'].append('malformed gate row')
    ends = re.findall(r'^PANIC_CAPTURE_END context_unchanged=([01]) resumes_guest=([01])$', text, re.M)
    callers = re.findall(r'^PANIC_CALLER known=([01]) saved_lr=([0-9A-F]{8}) r25=([0-9A-F]{8}) r26=([0-9A-F]{8}) r30=([0-9A-F]{8})$', text, re.M)
    if sum(line.startswith('PANIC_CAPTURE_END ') for line in text.splitlines())!=len(ends) or sum(line.startswith('PANIC_CALLER ') for line in text.splitlines())!=len(callers):result['errors'].append('malformed end/caller row')
    if len(gates) != 1 or gates[0] != ('1', '82390A6C') or ends != [('1', '0')]:
        result['errors'].append('missing, duplicate, mismatched gate/end or changed context')
    if len(callers) == 1:
        result['caller'] = dict(known=callers[0][0] == '1', saved_lr=int(callers[0][1],16),
                                r25=int(callers[0][2],16), r26=int(callers[0][3],16), r30=int(callers[0][4],16))
    else:
        result['errors'].append('missing or duplicate caller observation')
    pattern = re.compile(r'^PANIC_READ tag=([a-z_]+) guest=([0-9A-F]{8}) status=([a-z-]+) captured=(\d+) terminated=([01]) truncated=([01]) word_known=([01]) word=([0-9A-F]{8}) hex=([0-9A-F]*)$')
    for line in text.splitlines():
        if not line.startswith('PANIC_READ '):
            continue
        m=pattern.fullmatch(line)
        if not m:
            result['errors'].append('malformed bounded read row');continue
        tag, guest, status, count, terminated, truncated, known, word, raw=m.groups()
        if tag in result['reads']:
            result['errors'].append('duplicate bounded read tag');continue
        count=int(count)
        if count>8192 or len(raw)!=count*2 or (status!='ok' and count):
            result['errors'].append('invalid captured length/status');continue
        if known=='1' and (status!='ok' or count!=4 or int(raw,16)!=int(word,16)):
            result['errors'].append('inconsistent BE word row');continue
        row=dict(guest=int(guest,16),status=status,captured=count,terminated=terminated=='1',
                 truncated=truncated=='1',word_known=known=='1',word=int(word,16),hex=raw)
        if tag in ('message','filename') and status=='ok':
            try:
                data=bytes.fromhex(raw)
                if count%2 or terminated!='1' or truncated!='0' or not data.endswith(b'\0\0'):
                    raise ValueError('unterminated or truncated UTF16')
                decoded=data[:-2].decode('utf-16be',errors='strict')
                if '\0' in decoded:raise ValueError('unexpected interior NUL')
                row['text']=decoded
            except (ValueError,UnicodeError) as error:
                row['decode_error']=str(error)
        result['reads'][tag]=row
    msg=result['reads'].get('message',{})
    caller=result.get('caller',{})
    result['success']=bool(not result['errors'] and msg.get('guest')==0x8327C318 and 'text' in msg and 'decode_error' not in msg and caller.get('known') and caller.get('saved_lr')==0x824844F4)
    return result
