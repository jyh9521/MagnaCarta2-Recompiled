"""Independent movie framing, bounded observation, and provenance regression cases."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.research.movie_trace_report import (
    TARGETS, CAPACITY, parse_movie_trace, read_movie_traces,
)


class MovieTraceTests(unittest.TestCase):
    def text(self, kind=1, status='ok', name='csm_prologue.txt'):
        lines = ['TITLE_WAIT_SDK parent_attested=1',
                 'TITLE_MOVIE_TRACE enabled=1 code_guard=1 binding_guard=1 configured=1']
        lines += [f'MOVIE_BIND target={t:08X} dispatcher_hook=1 distinct_original=1' for t in TARGETS]
        lines += ['MOVIE_TRACE status=frozen capacity=4096 targets=9 total_capacity=36864 reserved=2 calls=1 posts=1 unwound=0 inflight=0 dropped=0 suppressed=0 frozen=1 weak_snapshot=1']
        for i, target in enumerate(TARGETS):
            n = int(i == kind)
            lines.append(f'MOVIE_TARGET kind={i} target={target:08X} reserved={n*2} pre={n} post={n} unwound=0 inflight=0 dropped=0 suppressed=0 frozen=1')
        args = ' '.join(f'r{i}={0x20000 if i == 3 else 0x30000 if i in (4,5) else 0:X}' for i in range(3, 11))
        if status == 'not-read' and kind in {1, 3, 4}:
            args = args.replace('r5=30000' if kind == 1 else 'r4=30000', 'r5=0' if kind == 1 else 'r4=0')
        obj = '20000' if kind in {1, 3, 4, 5, 6, 7, 8} else '0'
        known = 'F' if obj != '0' else '0'
        if kind not in {1, 2, 3, 4}: status = 'not-read'
        encoded = (name+'\0').encode('utf-16-be').hex().upper() if status == 'ok' else '-'
        for i, phase in enumerate(('pre', 'post')):
            lines.append(f'MOVIE_ENTRY slot={kind*CAPACITY+i} seq={i+1} call=1 parent=0 depth=1 target={TARGETS[kind]:08X} phase={phase} thread=1 context=1234 lr=1234 sp=10000 tick_ms={10+i*5} {args} result=0 obj={obj} known={known} w38=0 w50=0 w58=0 wB8=0 text_known=0 text_count=0 name_status={status} name_hex={encoded}')
        return '\n'.join(lines)+'\n'

    def parse(self, text): return parse_movie_trace(text, True)
    def bad(self, text):
        result = self.parse(text)
        self.assertFalse(result['capture_verified'], result)
        self.assertFalse(result['complete_within_snapshot'])
        self.assertTrue(result['errors'])

    def test_valid_all_targets(self):
        for kind in range(9):
            with self.subTest(kind=kind):
                result = self.parse(self.text(kind))
                self.assertTrue(result['capture_verified'], result['errors'])
                self.assertTrue(result['complete_within_snapshot'])
                self.assertFalse(result['playback_verified'])
                self.assertEqual(result['completed_calls'][0]['duration_ms'], 5)

    def test_utf16_non_ascii(self):
        result = self.parse(self.text(name='序章🎬.bik'))
        self.assertTrue(result['capture_verified'], result['errors'])
        self.assertEqual(result['entries'][0]['name'], '序章🎬.bik')

    def test_empty_name(self): self.assertTrue(self.parse(self.text(name=''))['capture_verified'])
    def test_95_unit_name(self): self.assertTrue(self.parse(self.text(name='a'*95))['capture_verified'])
    def test_96_unit_name_overflows(self): self.bad(self.text(name='a'*96))
    def test_disabled(self): self.assertEqual(parse_movie_trace('bogus')['status'], 'disabled')
    def test_faults_retained(self):
        for status in ('truncated', 'outside-ram', 'null-guest', 'invalid-view', 'invalid-count', 'guest-overflow', 'outside-span', 'host-overflow', 'query-failed', 'unreadable', 'partial-read', 'read-failed', 'not-read'):
            with self.subTest(status=status):
                result = self.parse(self.text(status=status))
                self.assertTrue(result['capture_verified'], result['errors'])
                self.assertIsNone(result['entries'][0]['name'])

    def test_guards(self):
        for old, new in [('parent_attested=1', 'parent_attested=0'), ('code_guard=1', 'code_guard=0'), ('binding_guard=1', 'binding_guard=0'), ('distinct_original=1', 'distinct_original=0'), ('dispatcher_hook=1', 'dispatcher_hook=0')]:
            with self.subTest(old=old): self.bad(self.text().replace(old, new, 1))
    def test_duplicate_binding(self): self.bad(self.text()+self.text().splitlines()[2])
    def test_duplicate_header(self): self.bad(self.text()+self.text().splitlines()[11])
    def test_duplicate_target(self): self.bad(self.text()+self.text().splitlines()[12])
    def test_duplicate_entry(self): self.bad(self.text()+self.text().splitlines()[-1])
    def test_duplicate_sequence(self): self.bad(self.text().replace('seq=2', 'seq=1'))
    def test_duplicate_phase(self): self.bad(self.text().replace('phase=post', 'phase=pre'))
    def test_schema_extra(self): self.bad(self.text().replace('w38=0', 'alien=0 w38=0'))
    def test_schema_missing(self): self.bad(self.text().replace(' w38=0', ''))
    def test_schema_duplicate(self): self.bad(self.text().replace('w38=0', 'w38=0 w38=0'))
    def test_unknown_frame(self): self.bad(self.text()+'MOVIE_BOGUS value=1')
    def test_bare_frame(self): self.bad(self.text()+'MOVIE_ENTRY')
    def test_number_limits(self):
        for old,new in [('r3=20000','r3=10000000000000000'),('thread=1','thread=4294967296'),('tick_ms=10','tick_ms=-1'),('tick_ms=10','tick_ms=18446744073709551616'),('known=F','known=10'),('obj=20000','obj=100000000'),('w38=0','w38=100000000'),('seq=2','seq=36865'),('depth=1','depth=0')]:
            with self.subTest(new=new): self.bad(self.text().replace(old,new))
    def test_known_zero_fields(self): self.bad(self.text().replace('known=F w38=0','known=0 w38=1'))
    def test_known_can_observe_zero(self): self.assertTrue(self.parse(self.text())['capture_verified'])
    def test_object_identity(self): self.bad(self.text().replace('obj=20000','obj=20004'))
    def test_outside_object_is_zero(self):
        text = self.text().replace('r3=20000','r3=1').replace('obj=20000 known=F','obj=0 known=0')
        self.assertTrue(self.parse(text)['capture_verified'])
    def test_outside_object_known_rejected(self): self.bad(self.text().replace('r3=20000','r3=1').replace('obj=20000','obj=0'))
    def test_unread_object_kind(self): self.bad(self.text(0).replace('obj=0 known=0','obj=20000 known=1'))
    def test_unread_name_kind(self): self.bad(self.text(0).replace('name_status=not-read','name_status=outside-ram'))
    def test_name_malformed(self):
        text=self.text(name='A')
        for old,new in [('name_status=ok','name_status=unknown'),('name_hex=00410000','name_hex=0041'),('name_hex=00410000','name_hex=000000410000'),('name_hex=00410000','name_hex=D8000000'),('name_hex=00410000','name_hex=xyz'),('name_hex=00410000','name_hex=000'),('name_status=ok','name_status=truncated')]:
            with self.subTest(new=new): self.bad(text.replace(old,new))
    def test_text_count(self):
        self.assertTrue(self.parse(self.text().replace('text_known=0 text_count=0', 'text_known=1 text_count=0'))['capture_verified'])
        self.assertTrue(self.parse(self.text(2).replace('text_known=0 text_count=0', 'text_known=1 text_count=F'))['capture_verified'])
        for fields in ('text_known=0 text_count=1', 'text_known=2 text_count=0', 'text_known=1 text_count=100000000'):
            self.bad(self.text().replace('text_known=0 text_count=0', fields))
        self.bad(self.text(0).replace('text_known=0 text_count=0', 'text_known=1 text_count=0'))

    def test_pair_identity(self): self.bad(self.text().replace('tick_ms=15 r3=20000','tick_ms=15 r3=30000'))
    def test_pair_time(self): self.bad(self.text().replace('tick_ms=15','tick_ms=5'))
    def test_pair_sequence(self): self.bad(self.text().replace('seq=1','seq=3'))
    def test_counter_below_observed(self): self.bad(self.text().replace('reserved=2 pre=1 post=1','reserved=2 pre=0 post=1'))
    def test_aggregate(self): self.bad(self.text().replace('reserved=2 calls=1','reserved=3 calls=1'))
    def test_missing_slot(self): self.bad('\n'.join(self.text().splitlines()[:-1]))
    def test_bad_slot(self): self.bad(self.text().replace('slot=4097','slot=36864'))
    def test_post_without_pre(self):
        text=self.text().splitlines();text[-2]=text[-1].replace('slot=4097','slot=4096').replace('seq=2','seq=1').replace('call=1','call=2')
        text='\n'.join(text).replace('reserved=2 pre=1 post=1','reserved=2 pre=1 post=2')
        self.bad(text)
    def test_pending_is_verified_not_complete(self):
        text='\n'.join(self.text().splitlines()[:-1])+'\nMOVIE_PENDING slot=4097\n'
        result=self.parse(text)
        self.assertTrue(result['capture_verified'],result['errors']);self.assertFalse(result['complete_within_snapshot'])
        self.assertEqual(len(result['incomplete_calls']),1)
    def test_unfinished_is_not_complete(self):
        text='\n'.join(self.text().splitlines()[:-1]).replace('reserved=2 calls=1 posts=1','reserved=1 calls=1 posts=0').replace('reserved=2 pre=1 post=1','reserved=1 pre=1 post=0')
        result=self.parse(text);self.assertTrue(result['capture_verified'],result['errors']);self.assertFalse(result['complete_within_snapshot'])
    def test_weak_counters_are_not_false_rejected(self):
        result=self.parse(self.text().replace('calls=1 posts=1','calls=1 posts=0'))
        self.assertTrue(result['capture_verified'],result['errors']);self.assertFalse(result['complete_within_snapshot'])
    def test_inflight_not_complete(self):
        result=self.parse(self.text().replace('inflight=0','inflight=1'))
        self.assertTrue(result['capture_verified']);self.assertFalse(result['complete_within_snapshot'])
    def test_saturated_pending_allowed(self):
        text=self.text().splitlines()[:-2]
        text='\n'.join(text).replace('reserved=2 calls=1','reserved=4097 calls=1').replace('reserved=2 pre=1 post=1','reserved=4097 pre=1 post=1').replace('dropped=0','dropped=1',1)
        text+='\n'+'\n'.join(f'MOVIE_PENDING slot={4096+i}' for i in range(4096))
        result=self.parse(text);self.assertTrue(result['capture_verified'],result['errors']);self.assertFalse(result['complete_within_snapshot'])
    def test_drop_overcount(self): self.bad(self.text().replace('dropped=0','dropped=1'))

    def nested(self):
        text=self.text().splitlines()
        text[11]=text[11].replace('reserved=2 calls=1 posts=1', 'reserved=4 calls=2 posts=2')
        text[14]=text[14].replace('reserved=0 pre=0 post=0','reserved=2 pre=1 post=1')
        pre, post=text[-2],text[-1].replace('seq=2','seq=4').replace('tick_ms=15','tick_ms=20')
        child=pre.replace('slot=4096','slot=8192').replace('seq=1','seq=2').replace('call=1 parent=0 depth=1','call=2 parent=1 depth=2').replace('target=82490CF0','target=827B6148').replace('obj=20000 known=F','obj=0 known=0').replace('tick_ms=10','tick_ms=12')
        childpost=child.replace('slot=8192','slot=8193').replace('seq=2','seq=3').replace('phase=pre','phase=post').replace('tick_ms=12','tick_ms=15')
        return '\n'.join(text[:-2]+[pre,child,childpost,post])+'\n'
    def test_nested(self):
        result=self.parse(self.nested());self.assertTrue(result['capture_verified'],result['errors']);self.assertTrue(result['complete_within_snapshot'])
    def test_nested_parent_thread(self): self.bad(self.nested().replace('target=827B6148 phase=pre thread=1','target=827B6148 phase=pre thread=2').replace('target=827B6148 phase=post thread=1','target=827B6148 phase=post thread=2'))
    def test_nested_parent_depth(self): self.bad(self.nested().replace('call=2 parent=1 depth=2','call=2 parent=1 depth=3'))
    def test_nested_parent_missing(self): self.bad(self.nested().replace('call=2 parent=1','call=3 parent=2'))
    def test_nested_after_parent_end(self): self.bad(self.nested().replace('seq=3 call=2','seq=5 call=2'))
    def test_nested_time_after_parent_end(self): self.bad(self.nested().replace('tick_ms=15','tick_ms=25'))
    def test_partial_state_can_change_between_phases(self):
        text=self.text().replace('tick_ms=15','tick_ms=15').splitlines()
        text[-1]=text[-1].replace('w38=0','w38=1').replace('text_known=0 text_count=0','text_known=1 text_count=2')
        result=self.parse('\n'.join(text));self.assertTrue(result['capture_verified'],result['errors'])

    def reader(self, suffix='', missing=False, raw=None):
        lines=self.text().splitlines()
        data=('\n'.join(lines[11:])+'\n').encode() if raw is None else raw
        with tempfile.TemporaryDirectory() as directory:
            if not missing: Path(directory,'movie-trace-0.txt').write_bytes(data)
            run='\n'.join(lines[:11])+'\nMOVIE_TRACE_FILE reason=boundary path=movie-trace-0.txt success=1\n'+suffix
            result,captures=read_movie_traces(run,directory,True)
            if captures:self.assertEqual(captures[0]['sha256'],hashlib.sha256(data).hexdigest())
            return result
    def test_read_file(self): self.assertTrue(self.reader()['capture_verified'])
    def test_read_missing(self): self.assertFalse(self.reader(missing=True)['capture_verified'])
    def test_read_duplicate(self): self.assertFalse(self.reader('MOVIE_TRACE_FILE reason=boundary path=movie-trace-0.txt success=1')['capture_verified'])
    def test_read_failure(self): self.assertFalse(self.reader('MOVIE_TRACE_FILE reason=fault path=movie-trace-1.txt success=0')['capture_verified'])
    def test_read_traversal(self): self.assertFalse(self.reader('MOVIE_TRACE_FILE reason=boundary path=../movie-trace-1.txt success=1')['capture_verified'])
    def test_read_unexpected_path(self): self.assertFalse(self.reader('MOVIE_TRACE_FILE reason=boundary path=other.txt success=1')['capture_verified'])
    def test_read_invalid_utf8(self): self.assertFalse(self.reader(raw=b'\xff')['capture_verified'])
    def test_read_exception(self):
        with patch.object(Path,'read_bytes',side_effect=OSError('retained failure')): self.assertFalse(self.reader()['capture_verified'])
    def test_reader_disabled_no_io(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('must not read')):
            result,captures=read_movie_traces('MOVIE_TRACE_FILE reason=x path=movie-trace-0.txt success=1','.',False)
            self.assertEqual(result['status'],'disabled');self.assertEqual(captures,[])
    def test_read_index_bound(self): self.assertFalse(self.reader('MOVIE_TRACE_FILE reason=boundary path=movie-trace-4.txt success=1')['capture_verified'])
    def test_read_hardlink(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'original.txt').write_text(self.text())
            os.link(root/'original.txt', root/'movie-trace-0.txt')
            result,_=read_movie_traces('MOVIE_TRACE_FILE reason=x path=movie-trace-0.txt success=1',root,True)
            self.assertIn('capture hard link',result['errors'])
    def test_read_size_bound(self):
        from types import SimpleNamespace
        with patch.object(Path,'stat',return_value=SimpleNamespace(st_nlink=1,st_size=32*1024*1024+1,st_mode=0o100644)):
            with patch.object(Path,'read_bytes',side_effect=AssertionError('must not read oversized')):
                self.assertFalse(self.reader()['capture_verified'])
    def test_nonnull_name_notread(self):
        self.bad(self.text(status='not-read').replace('r5=0','r5=1'))
    def test_kind2_null_fstring_contents(self):
        self.assertTrue(self.parse(self.text(2,status='not-read'))['capture_verified'])
    def test_read_requires_provenance(self):
        with tempfile.TemporaryDirectory() as directory:self.assertFalse(read_movie_traces(self.text(),directory,True)[0]['capture_verified'])
    def test_duplicate_attestation_inside_file(self):
        self.assertFalse(self.reader(raw=self.text().encode())['capture_verified'])


if __name__ == '__main__': unittest.main()
