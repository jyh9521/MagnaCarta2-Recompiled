"""Validate bounded movie RAW-hook snapshots; never infer playback or causality.

Counters are weak snapshots, not an atomic guest-execution boundary. A verified
capture can be incomplete, saturated, or contain an unfinished delegate.
"""
import hashlib
import re
from pathlib import Path

TARGETS = (0x8248FED8, 0x82490CF0, 0x827B6148, 0x82490708, 0x824909B8,
           0x82490C78, 0x82491630, 0x82491930, 0x82491BD8)
CAPACITY = 4096
MAX_CAPTURE_BYTES = 32 * 1024 * 1024
HEX = {'target', 'context', 'lr', 'sp', 'result', 'obj', 'known',
       'w38', 'w50', 'w58', 'wB8', 'text_count'} | {f'r{i}' for i in range(3, 11)}
STRINGS = {'status', 'phase', 'name_status', 'name_hex'}
READ_ERRORS = {'invalid-view', 'null-guest', 'invalid-count', 'guest-overflow',
               'outside-span', 'host-overflow', 'query-failed', 'unreadable',
               'partial-read', 'read-failed', 'outside-ram'}
OBJECT_KINDS = {1, 3, 4, 5, 6, 7, 8}
NAME_KINDS = {1, 2, 3, 4}
WORDS = ('w38', 'w50', 'w58', 'wB8')


def fields(line):
    row = {}
    for token in line.split()[1:]:
        key, sep, value = token.partition('=')
        if not sep or not value or key in row:
            raise ValueError('malformed/duplicate field')
        if key in STRINGS:
            row[key] = value
            continue
        base = 16 if key in HEX else 10
        if not re.fullmatch(r'[0-9A-Fa-f]{1,16}' if base == 16 else r'[0-9]{1,20}', value):
            raise ValueError('invalid number')
        row[key] = int(value, base)
        if row[key] >= 2**64:
            raise ValueError('overflow')
    return row


def _observe(row, kind):
    if row['known'] > 15 or row['obj'] > 0xFFFFFFFF:
        raise ValueError('object width')
    if kind not in OBJECT_KINDS and (row['obj'] or row['known']):
        raise ValueError('unrequested object')
    original = row['r3'] & 0xFFFFFFFF
    expected_obj = original if kind in OBJECT_KINDS and 0x10000 <= original <= 0x7EFFFF44 else 0
    if row['obj'] != expected_obj or (not row['obj'] and row['known']):
        raise ValueError('object identity')
    for bit, key in enumerate(WORDS):
        if row[key] > 0xFFFFFFFF or (not row['known'] & (1 << bit) and row[key]):
            raise ValueError('unknown/non-word field')
    if row['text_known'] not in {0, 1} or row['text_count'] > 0xFFFFFFFF or (not row['text_known'] and row['text_count']) or (kind == 0 and row['text_known']):
        raise ValueError('text count known/width')
    status, value = row['name_status'], row['name_hex']
    if kind not in NAME_KINDS:
        if (status, value) != ('not-read', '-'):
            raise ValueError('unrequested name')
        row['name'] = None
        return
    if status == 'not-read':
        direct_name = row['r5' if kind == 1 else 'r4'] & 0xFFFFFFFF
        if kind != 2 and direct_name:
            raise ValueError('non-null name not read')
        if value != '-':
            raise ValueError('unread name payload')
        row['name'] = None
        return
    if status not in READ_ERRORS | {'ok', 'truncated'}:
        raise ValueError('name status')
    if status != 'ok':
        if value != '-':
            raise ValueError('fault/truncation name payload')
        row['name'] = None
        return
    if not re.fullmatch(r'(?:[0-9a-fA-F]{4}){1,96}', value):
        raise ValueError('name hex/size')
    raw = bytes.fromhex(value)
    units = [raw[i:i+2] for i in range(0, len(raw), 2)]
    if units[-1] != b'\0\0' or b'\0\0' in units[:-1]:
        raise ValueError('name terminator')
    try:
        row['name'] = raw[:-2].decode('utf-16-be')
    except UnicodeDecodeError:
        raise ValueError('invalid UTF-16') from None


def parse_movie_trace(text, requested=False):
    result = dict(status='invalid_capture' if requested else 'disabled',
                  capture_verified=False, complete_within_snapshot=False,
                  entries=[], errors=[], pending=[], completed_calls=[],
                  incomplete_calls=[], playback_verified=False,
                  scope='Bounded weak movie-call observations; not playback, script execution, black-screen causality, or complete guest coverage.')
    if not requested:
        return result
    try:
        lines = text.splitlines()
        if [x for x in lines if x.startswith('TITLE_WAIT_SDK')] != ['TITLE_WAIT_SDK parent_attested=1']:
            raise ValueError('SDK attestation')
        if [x for x in lines if x.startswith('TITLE_MOVIE_TRACE')] != ['TITLE_MOVIE_TRACE enabled=1 code_guard=1 binding_guard=1 configured=1']:
            raise ValueError('configuration/code guard')
        binds = [fields(x) for x in lines if x.startswith('MOVIE_BIND')]
        if len(binds) != len(TARGETS) or {x.get('target') for x in binds} != set(TARGETS) or any(set(x) != {'target', 'dispatcher_hook', 'distinct_original'} or x['dispatcher_hook'] != 1 or x['distinct_original'] != 1 for x in binds):
            raise ValueError('binding guard')
        headers = [fields(x) for x in lines if x.startswith('MOVIE_TRACE') and not x.startswith('MOVIE_TRACE_FILE')]
        keys = {'status', 'capacity', 'targets', 'total_capacity', 'reserved', 'calls', 'posts', 'unwound', 'inflight', 'dropped', 'suppressed', 'frozen', 'weak_snapshot'}
        if len(headers) != 1:
            raise ValueError('unique header')
        h = headers[0]
        if set(h) != keys or (h['status'], h['capacity'], h['targets'], h['total_capacity'], h['frozen'], h['weak_snapshot']) != ('frozen', CAPACITY, len(TARGETS), CAPACITY*len(TARGETS), 1, 1):
            raise ValueError('header contract')
        targets, entries, events = {}, {}, {}
        pending, sequences = set(), set()
        for line in lines:
            if not line.startswith('MOVIE_') or line.startswith(('MOVIE_BIND ', 'MOVIE_TRACE ', 'MOVIE_TRACE_FILE ')):
                continue
            token = line.split()[0]
            if token not in {'MOVIE_TARGET', 'MOVIE_ENTRY', 'MOVIE_PENDING'}:
                raise ValueError('unknown/malformed movie frame')
            row = fields(line)
            if token == 'MOVIE_TARGET':
                if set(row) != {'kind', 'target', 'reserved', 'pre', 'post', 'unwound', 'inflight', 'dropped', 'suppressed', 'frozen'} or row['kind'] >= len(TARGETS) or row['target'] != TARGETS[row['kind']] or row['kind'] in targets or row['frozen'] != 1 or row['reserved'] >= 2**63:
                    raise ValueError('target contract')
                targets[row['kind']] = row
                continue
            slot = row['slot']
            if slot >= CAPACITY*len(TARGETS) or slot in entries or slot in pending:
                raise ValueError('slot duplicate/range')
            if token == 'MOVIE_PENDING':
                if set(row) != {'slot'}:
                    raise ValueError('pending contract')
                pending.add(slot)
                continue
            expected = {'slot', 'seq', 'call', 'parent', 'depth', 'target', 'phase', 'thread', 'context', 'lr', 'sp', 'tick_ms', 'result', 'obj', 'known', 'text_known', 'text_count', 'name_status', 'name_hex'} | set(WORDS) | {f'r{i}' for i in range(3, 11)}
            if set(row) != expected or row['target'] != TARGETS[slot//CAPACITY] or row['phase'] not in {'pre', 'post'} or not row['call'] or not row['seq'] or not row['depth'] or row['seq'] in sequences or row['seq'] > CAPACITY*len(TARGETS):
                raise ValueError('entry contract')
            if bool(row['parent']) != (row['depth'] > 1) or row['parent'] >= row['call'] or row['thread'] > 0xFFFFFFFF:
                raise ValueError('nesting/width')
            event = row['call'], row['phase']
            if event in events:
                raise ValueError('duplicate call phase')
            _observe(row, slot//CAPACITY)
            sequences.add(row['seq']); events[event] = row; entries[slot] = row
        if set(targets) != set(range(len(TARGETS))):
            raise ValueError('missing target')
        if sum(t['reserved'] for t in targets.values()) != h['reserved']:
            raise ValueError('reserved aggregate')
        for kind, t in targets.items():
            actual = {s for s in entries.keys() | pending if s//CAPACITY == kind}
            if actual != set(range(kind*CAPACITY, kind*CAPACITY+min(t['reserved'], CAPACITY))):
                raise ValueError('truncated slots')
            if t['dropped'] > max(0, t['reserved']-CAPACITY):
                raise ValueError('drop accounting')
            observed = [e for e in entries.values() if e['slot']//CAPACITY == kind]
            if any(sum(e['phase'] == phase for e in observed) > t[count] for phase, count in [('pre', 'pre'), ('post', 'post')]):
                raise ValueError('counter below observed events')
        storage = not pending and all(t['reserved'] < CAPACITY and not t['dropped'] for t in targets.values())
        complete, incomplete = [], []
        for call in sorted({e[0] for e in events}):
            pre, post = events.get((call, 'pre')), events.get((call, 'post'))
            if not pre or not post:
                incomplete.append(dict(call=call, pre=pre, post=post))
                continue
            if any(pre[k] != post[k] for k in ['target', 'parent', 'depth', 'thread', 'context'] + [f'r{i}' for i in range(3, 11)]) or pre['seq'] >= post['seq'] or pre['tick_ms'] > post['tick_ms']:
                raise ValueError('pair identity/time')
            complete.append(dict(call=call, pre=pre, post=post, duration_ms=post['tick_ms']-pre['tick_ms']))
        for e in entries.values():
            if e['phase'] == 'post' and (e['call'], 'pre') not in events and storage:
                raise ValueError('post without pre')
            if not e['parent']:
                continue
            parent, end = events.get((e['parent'], 'pre')), events.get((e['parent'], 'post'))
            if parent is None:
                if storage: raise ValueError('missing parent')
                continue
            if e['thread'] != parent['thread'] or e['depth'] != parent['depth']+1 or e['seq'] <= parent['seq'] or e['tick_ms'] < parent['tick_ms']:
                raise ValueError('parent thread/depth/start')
            if end and (e['seq'] >= end['seq'] or e['tick_ms'] > end['tick_ms']):
                raise ValueError('child after parent end')
        balanced = storage and not incomplete and all(not t[k] for t in targets.values() for k in ('unwound', 'inflight', 'suppressed'))
        balanced = balanced and all(t['reserved'] == t['pre']+t['post'] and t['pre'] == t['post'] for t in targets.values())
        balanced = balanced and all(h[k] == sum(t['pre' if k == 'calls' else 'post' if k == 'posts' else k] for t in targets.values()) for k in ('calls', 'posts', 'unwound', 'inflight', 'dropped', 'suppressed'))
        result.update(status='observed', capture_verified=True, complete_within_snapshot=balanced,
                      header=h, targets=[targets[i] for i in range(len(TARGETS))],
                      entries=sorted(entries.values(), key=lambda e:e['seq']), pending=sorted(pending),
                      completed_calls=complete, incomplete_calls=incomplete, storage_complete=storage)
    except (ValueError, KeyError, TypeError) as exc:
        result['errors'].append(str(exc))
    return result


def read_movie_traces(run_text, output, requested=False):
    result = parse_movie_trace(run_text, requested)
    if not requested:
        return result, []
    captures, errors, seen = [], [], set()
    root = Path(output).resolve()
    for line in run_text.splitlines():
        if not line.startswith('MOVIE_TRACE_FILE'):
            continue
        match = re.fullmatch(r'MOVIE_TRACE_FILE reason=([A-Za-z0-9_-]+) path=(movie-trace-[0-3]\.txt) success=([01])', line)
        if not match:
            errors.append('malformed file declaration'); continue
        reason, name, success = match.groups()
        if name in seen:
            errors.append('duplicate file'); continue
        seen.add(name)
        path = root/name
        try:
            if path.resolve().parent != root or path.is_symlink():
                raise ValueError('file escapes capture directory')
            if success != '1' or not path.is_file():
                raise ValueError('failed/missing file')
            metadata = path.stat()
            if metadata.st_nlink != 1:
                raise ValueError('capture hard link')
            if metadata.st_size > MAX_CAPTURE_BYTES:
                raise ValueError('capture too large')
            raw = path.read_bytes()
            if len(raw) > MAX_CAPTURE_BYTES:
                raise ValueError('capture too large')
            digest = hashlib.sha256(raw).hexdigest()
            text = raw.decode('utf-8', errors='strict')
            parsed = parse_movie_trace(run_text+'\n'+text, True)
            parsed.update(reason=reason, path=str(path), sha256=digest)
            captures.append(parsed)
            if not parsed['capture_verified']:
                errors.extend(parsed['errors'])
        except (OSError, ValueError, UnicodeError) as exc:
            errors.append(str(exc))
    if not captures:
        errors.append('no captured file provenance')
    else:
        result = dict(captures[-1])
    if errors:
        result.update(status='invalid_capture', capture_verified=False, complete_within_snapshot=False, errors=errors)
    return result, captures
