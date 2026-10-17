import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from tools.research.frame_timeline_report import parse_frame_timeline,read_frame_timelines,TARGETS
class TimelineReportTests(unittest.TestCase):
    def text(self):
        lines=['TITLE_WAIT_SDK parent_attested=1','TITLE_FRAME_TIMELINE enabled=1 code_guard=1 binding_guard=1 configured=1']
        lines +=[f'TIMELINE_BIND target={t:08X} dispatcher_hook=1 distinct_original=1'for t in TARGETS]
        lines +=['TIMELINE_TRACE status=frozen capacity=8192 targets=5 total_capacity=40960 reserved=2 calls=1 posts=1 unwound=0 inflight=0 dropped=0 suppressed=0 frozen=1 weak_snapshot=1']
        for i,t in enumerate(TARGETS):lines.append(f'TIMELINE_TARGET kind={i} target={t:08X} reserved={2 if i==0 else 0} pre={1 if i==0 else 0} post={1 if i==0 else 0} unwound=0 inflight=0 dropped=0 suppressed=0 frozen=1')
        args=' '.join(f'r{i}=0'for i in range(3,11))
        for i,phase in enumerate(['pre','post']):lines.append(f'TIMELINE_ENTRY slot={i} seq={i+1} call=1 parent=0 depth=1 target={TARGETS[0]:08X} phase={phase} thread=1 context=1234 lr=1234 sp=10000 tick_ms={10+i*5} '+args+' result=0')
        return '\n'.join(lines)+'\n'
    def bad(self,s):self.assertFalse(parse_frame_timeline(s,True)['capture_verified'])
    def test_valid(self):
        j=parse_frame_timeline(self.text(),True);self.assertTrue(j['capture_verified'],j['errors']);self.assertEqual(j['completed_calls'][0]['duration_ms'],5)
    def test_disabled(self):self.assertEqual(parse_frame_timeline('')['status'],'disabled')
    def test_no_frame_proof(self):self.assertFalse(parse_frame_timeline(self.text(),True)['visible_frame_proof'])
    def test_no_coverage_claim(self):self.assertFalse(parse_frame_timeline(self.text(),True)['coverage_complete'])
    def test_missing_header(self):self.bad(self.text().replace('TIMELINE_TRACE','OTHER_TRACE'))
    def test_missing_sdk(self):self.bad(self.text().replace('parent_attested=1','parent_attested=0'))
    def test_guard(self):self.bad(self.text().replace('code_guard=1','code_guard=0'))
    def test_missing_binding(self):self.bad(self.text().replace('dispatcher_hook=1','dispatcher_hook=0',1))
    def test_unknown_frame(self):self.bad(self.text()+'TIMELINE_BOGUS x=1')
    def test_bare_frame(self):self.bad(self.text()+'TIMELINE_ENTRY')
    def test_truncation(self):self.bad('\n'.join(self.text().splitlines()[:-1]))
    def test_immutable_args(self):self.bad(self.text().replace('tick_ms=15 r3=0','tick_ms=15 r3=1'))
    def test_bad_time(self):self.bad(self.text().replace('tick_ms=15','tick_ms=5'))
    def test_parent_depth(self):self.bad(self.text().replace('parent=0 depth=1','parent=0 depth=2'))
    def test_hex_width(self):self.bad(self.text().replace('context=1234','context=10000000000000000'))
    def test_duplicate_slot(self):self.bad(self.text()+self.text().splitlines()[-1])
    def test_pending(self):
        s='\n'.join(self.text().splitlines()[:-1])+'\nTIMELINE_PENDING slot=1\n';j=parse_frame_timeline(s,True);self.assertTrue(j['capture_verified']);self.assertFalse(j['storage_complete']);self.assertEqual(len(j['incomplete_calls']),1)
    def load(self,suffix='',missing=False):
        with tempfile.TemporaryDirectory()as d:
            lines=self.text().splitlines();raw='\n'.join(lines[7:]);run='\n'.join(lines[:7])+'\nFRAME_TIMELINE_FILE reason=boundary path=frame-timeline-0.txt success=1\n'+suffix
            if not missing:Path(d,'frame-timeline-0.txt').write_text(raw)
            return read_frame_timelines(run,d,True)[0]
    def test_load(self):self.assertTrue(self.load()['capture_verified'])
    def test_missing_file(self):self.assertFalse(self.load(missing=True)['capture_verified'])
    def test_later_failure(self):self.assertFalse(self.load('FRAME_TIMELINE_FILE reason=fault path=frame-timeline-1.txt success=0')['capture_verified'])
    def test_duplicate_file(self):self.assertFalse(self.load('FRAME_TIMELINE_FILE reason=boundary path=frame-timeline-0.txt success=1')['capture_verified'])
    def test_unreadable_file(self):
        with patch.object(Path,'read_bytes',side_effect=OSError('retained')):self.assertFalse(self.load()['capture_verified'])

    def nested(self):
        lines=self.text().splitlines();lines[7]=lines[7].replace('reserved=2 calls=1 posts=1','reserved=4 calls=2 posts=2')
        lines[9]=lines[9].replace('reserved=0 pre=0 post=0','reserved=2 pre=1 post=1')
        pre=lines[-2];post=lines[-1].replace('seq=2','seq=4').replace('tick_ms=15','tick_ms=20')
        childpre=pre.replace('slot=0','slot=8192').replace('seq=1','seq=2').replace('call=1 parent=0 depth=1','call=2 parent=1 depth=2').replace('target=8277B6D8','target=8244A360').replace('tick_ms=10','tick_ms=12')
        childpost=childpre.replace('slot=8192','slot=8193').replace('seq=2','seq=3').replace('phase=pre','phase=post').replace('tick_ms=12','tick_ms=15')
        return '\n'.join(lines[:-2]+[pre,childpre,childpost,post])+'\n'
    def test_nested(self):self.assertTrue(parse_frame_timeline(self.nested(),True)['capture_verified'])
    def test_parent_thread(self):self.bad(self.nested().replace('call=2 parent=1 depth=2 target=8244A360 phase=pre thread=1','call=2 parent=1 depth=2 target=8244A360 phase=pre thread=2').replace('call=2 parent=1 depth=2 target=8244A360 phase=post thread=1','call=2 parent=1 depth=2 target=8244A360 phase=post thread=2'))
    def test_nested_parent_depth(self):self.bad(self.nested().replace('call=2 parent=1 depth=2','call=2 parent=1 depth=3'))
    def test_parent_end_time(self):self.bad(self.nested().replace('tick_ms=15','tick_ms=25'))
    def test_parent_end_sequence(self):self.bad(self.nested().replace('seq=3 call=2','seq=5 call=2'))
    def test_missing_parent(self):self.bad(self.nested().replace('call=2 parent=1','call=3 parent=2'))

    def test_reader_requires_file_provenance(self):
        with tempfile.TemporaryDirectory()as d:self.assertFalse(read_frame_timelines(self.text(),d,True)[0]['capture_verified'])
