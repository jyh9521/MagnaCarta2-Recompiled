"""Read completed, bounded input-probe logs; never reads a live SDK snapshot."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import struct

MAGIC = 0x373343415254324D
CAPACITY = 65536
EVENT = struct.Struct('<QQQIIIIII')
STREAM_BYTES = 16 + CAPACITY * EVENT.size
FILE_BYTES = 24 + 2 * STREAM_BYTES
NAMES = {1: 'request', 2: 'delegate_enter', 3: 'enumerate_enter',
         4: 'enumerate_leave', 5: 'delegate_leave', 6: 'return',
         7: 'shutdown_enter', 8: 'shutdown_leave'}


def read_trace(data: bytes) -> dict:
    if len(data) != FILE_BYTES:
        raise ValueError('trace size mismatch')
    if struct.unpack_from('<QQQ', data) != (MAGIC, 1, FILE_BYTES):
        raise ValueError('trace identity mismatch')
    events, dropped = [], 0
    for worker in range(2):
        start = 24 + worker * STREAM_BYTES
        count, lost = struct.unpack_from('<QQ', data, start)
        if count > CAPACITY:
            raise ValueError('invalid committed count')
        dropped += lost
        previous = 0
        for index in range(count):
            row = dict(zip(('sequence', 'object', 'argument', 'thread', 'api',
                            'iteration', 'kind', 'gated', 'depth'),
                           EVENT.unpack_from(data, start + 16 + index * EVENT.size)))
            if row['sequence'] <= previous or row['kind'] not in NAMES or row['gated'] not in (0, 1):
                raise ValueError('invalid event')
            previous = row['sequence']
            row['worker'] = worker
            events.append(row)
    events.sort(key=lambda x: x['sequence'])
    if len({e['sequence'] for e in events}) != len(events):
        raise ValueError('duplicate sequence')
    active, peak, overlap = {}, 0, []
    counts = {name: 0 for name in NAMES.values()}
    for row in events:
        kind = row['kind']
        counts[NAMES[kind]] += 1
        key = (row['thread'], row['api'], row['iteration'])
        if kind == 2:
            if key in active:
                raise ValueError('duplicate delegate entry')
            if len(overlap) < 8:
                overlap.extend({'left': old, 'right': row} for old in active.values()
                               if old['object'] == row['object'] and old['thread'] != row['thread'])
            active[key] = row
            peak = max(peak, len(active))
        elif kind == 5:
            if key not in active:
                raise ValueError('unpaired delegate leave')
            del active[key]
    return dict(events=len(events), dropped=dropped, saturated=bool(dropped), counts=counts,
                objects=sorted({e['object'] for e in events}),
                workers={str(w): sorted({e['thread'] for e in events if e['worker'] == w and e['kind'] <= 6}) for w in range(2)},
                gated=sorted({e['gated'] for e in events if e['kind'] == 2}),
                delegate_peak=peak, overlap=overlap[:8], unfinished=list(active.values()),
                tail=events[-16:], observation='API boundary order, not internal container write order')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('trace', type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    result = read_trace(args.trace.read_bytes())
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({k: result[k] for k in ('events', 'dropped', 'delegate_peak', 'gated', 'counts')}))


if __name__ == '__main__':
    main()
