"""Parse caller-gated read-only critical-section AV observations.

Not seeing this optional fault is not a title failure. Read results are post-fault
observations, not an atomic snapshot or proof of an object's type/lifetime.
"""
from __future__ import annotations
import re


def parse_critical_section_capture(text, requested=False):
    result = {'requested': bool(requested), 'success': False,
              'status': 'not_observed' if requested else 'disabled',
              'reads': {}, 'errors': [],
              'scope': 'Post-fault bounded read-only observations, not an atomic snapshot or root-cause proof.'}
    lines = [line for line in text.splitlines() if line.startswith('CRITICAL_')]
    if not lines:
        return result
    result['requested'] = True
    gate_re = re.compile(r'CRITICAL_GATE requested=1 matched=([01]) sdk_pc=([01]) sdk_bytes=([01]) caller_bytes=([01]) host_fault=([01]) host_rcx=([01]) lr=([0-9A-F]{8})')
    ppc_re = re.compile(r'CRITICAL_PPC r3=([0-9A-F]{16}) r11=([0-9A-F]{16}) r29=([0-9A-F]{16}) r30=([0-9A-F]{16})')
    end_re = re.compile(r'CRITICAL_CAPTURE_END context_unchanged=([01]) host_context_unchanged=([01]) resumes_guest=([01])')
    read_re = re.compile(r'CRITICAL_READ tag=([a-z_]+) guest=([0-9A-F]{8}) requested=(\d+) status=([a-z-]+) captured=(\d+) word_known=([01]) word=([0-9A-F]{8}) hex=([0-9A-F]*)')
    gates, ppcs, ends, read_rows = [], [], [], []
    for line in lines:
        for pattern, target in ((gate_re, gates), (ppc_re, ppcs), (end_re, ends), (read_re, read_rows)):
            match = pattern.fullmatch(line)
            if match:
                target.append(match.groups()); break
        else:
            result['errors'].append('malformed or unknown critical capture row')
    if len(gates) != 1:
        result['errors'].append('missing or duplicate gate')
    if len(ends) != 1 or ends[0] != ('1', '1', '0'):
        result['errors'].append('missing end, changed context, or resumed guest')
    gate = gates[0] if len(gates) == 1 else None
    if gate:
        result['gate'] = dict(zip(('matched', 'sdk_pc', 'sdk_bytes', 'caller_bytes', 'host_fault', 'host_rcx'),
                                  (value == '1' for value in gate[:6])))
        result['gate']['lr'] = int(gate[6], 16)
    if gate and gate[0] == '0' and not ppcs and not read_rows and not result['errors']:
        result['status'] = 'gate_rejected'
        return result
    if not gate or gate[:6] != ('1',) * 6 or gate[6] != '823BF2B8':
        result['errors'].append('SDK PC/bytes, caller bytes/LR, or host fault relation not matched')
    if len(ppcs) == 1:
        result['ppc'] = dict(zip(('r3', 'r11', 'r29', 'r30'), (int(v, 16) for v in ppcs[0])))
    else:
        result['errors'].append('missing or duplicate PPC context')
    statuses = {'ok', 'invalid-view', 'null-guest', 'invalid-count', 'guest-overflow', 'outside-span',
                'host-overflow', 'query-failed', 'unreadable', 'partial-read', 'read-failed'}
    expected_sizes = {'entry_word': 4, 'entry_prefix': 64, 'critical_prefix': 32}
    for tag, guest, wanted, status, count, known, word, raw in read_rows:
        wanted, count, word = int(wanted), int(count), int(word, 16)
        if tag in result['reads'] or tag not in expected_sizes:
            result['errors'].append('duplicate or unknown read tag'); continue
        if status not in statuses or wanted != expected_sizes[tag] or count > wanted or len(raw) != count * 2:
            result['errors'].append('invalid bounded read metadata'); continue
        if status != 'ok' and (count or raw or known != '0' or word):
            result['errors'].append('failed read exposed a prefix or word'); continue
        if status == 'ok' and count != wanted:
            result['errors'].append('successful read incomplete'); continue
        if known == '1' and (status != 'ok' or tag != 'entry_word' or count != 4 or int(raw, 16) != word):
            result['errors'].append('inconsistent BE word'); continue
        if known == '0' and word or status == 'ok' and tag == 'entry_word' and known != '1':
            result['errors'].append('inconsistent word-known metadata'); continue
        result['reads'][tag] = {'guest': int(guest, 16), 'requested': wanted, 'status': status,
                                'captured': count, 'word_known': known == '1', 'word': word, 'hex': raw}
    if set(result['reads']) != set(expected_sizes):
        result['errors'].append('missing bounded read rows')
    ppc = result.get('ppc')
    if ppc and len(result['reads']) == 3:
        obj, cs = ppc['r29'] & 0xFFFFFFFF, ppc['r3'] & 0xFFFFFFFF
        expected = {'entry_word': obj + 8 if obj <= 0xFFFFFFF7 else 0,
                    'entry_prefix': obj, 'critical_prefix': cs}
        if any(result['reads'][tag]['guest'] != value for tag, value in expected.items()):
            result['errors'].append('read address differs from original context relationship')
        field = result['reads']['entry_word']; prefix = result['reads']['entry_prefix']
        relations = {'field_known': field['word_known'], 'r30_matches_r3': (ppc['r30'] & 0xFFFFFFFF) == cs,
                     'r11_matches_field': (ppc['r11'] & 0xFFFFFFFF) == field['word'] if field['word_known'] else None}
        if field['word_known']:
            relations['field_plus4'] = (field['word'] + 4) & 0xFFFFFFFF
            relations['r3_matches'] = relations['field_plus4'] == cs
            if prefix['captured'] == 64:
                relations['prefix_word_matches'] = int(prefix['hex'][16:24], 16) == field['word']
        result['relations'] = relations
    result['success'] = not result['errors']
    result['status'] = 'captured' if result['success'] else 'invalid_capture'
    return result
