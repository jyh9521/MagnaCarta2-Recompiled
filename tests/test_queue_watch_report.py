import unittest
from tools.research.queue_watch_report import parse_queue_watch

class QueueWatchReportTests(unittest.TestCase):
    def text(self):
        fields={f'x{i}':0 for i in range(20)};fields.update(x2=0x40000000,x3=0x40000004,x4=0x40000004,x7=0x40000000,x9=0x82153638,x10=0x825C3508,x11=0x82399738,x12=0x82399768)
        return 'TITLE_WAIT_SDK parent_attested=1\nTITLE_COUNTER_TRACE enabled=1 code_guard=1 binding_guard=1 configured=1\nQUEUE_WATCH_TRACE status=frozen capacity=128 reserved=1 dropped=0 frozen=1 weak_snapshot=1 counter=83265218 global=83263ACC manager=83276B18\nQUEUE_WATCH_ENTRY slot=0 tick_ms=1 status=captured flags=00001E9C '+ ' '.join(f'{k}={v:X}' for k,v in fields.items())+' head_captured=4 head_status=ok head_hex=82153638 table_captured=12 table_status=ok table_hex=825C35088239973882399768\n'
    def test_valid(self):self.assertTrue(parse_queue_watch(self.text(),True)['capture_verified'])
    def test_disabled(self):self.assertEqual(parse_queue_watch(self.text())['status'],'disabled')
    def test_no_execution_claim(self):self.assertFalse(parse_queue_watch(self.text(),True)['executed_callback_proof'])
    def test_truncated(self):self.assertFalse(parse_queue_watch(self.text().replace('reserved=1','reserved=2'),True)['capture_verified'])
    def test_bad_body(self):self.assertFalse(parse_queue_watch(self.text().replace('code_guard=1','code_guard=0'),True)['capture_verified'])
    def test_mismatch(self):self.assertFalse(parse_queue_watch(self.text().replace('x11=82399738','x11=82399739'),True)['capture_verified'])
    def test_duplicate(self):self.assertFalse(parse_queue_watch(self.text()+self.text().splitlines()[-1],True)['capture_verified'])
    def test_bad_width(self):self.assertFalse(parse_queue_watch(self.text().replace('head_captured=4','head_captured=33'),True)['capture_verified'])
    def test_drop(self):self.assertFalse(parse_queue_watch(self.text().replace('dropped=0','dropped=1'),True)['capture_verified'])
    def test_pending(self):
        s=self.text().split('QUEUE_WATCH_ENTRY')[0]+'QUEUE_WATCH_PENDING slot=0\n';j=parse_queue_watch(s,True);self.assertTrue(j['capture_verified']);self.assertFalse(j['storage_complete'])
    def test_empty_prefix(self):
        s=self.text().replace('status=captured','status=empty').replace('flags=00001E9C','flags=0000009C').replace('x4=40000004','x4=40000000').replace('head_captured=4','head_captured=0').replace('head_status=ok','head_status=not-read').replace('table_status=ok','table_status=not-read').replace('head_hex=82153638','head_hex=').replace('table_captured=12','table_captured=0').replace('table_hex=825C35088239973882399768','table_hex=');
        for k in ['x9','x10','x11','x12']:
            import re
            s=re.sub(k+r'=[0-9A-F]+',k+'=0',s)
        self.assertTrue(parse_queue_watch(s,True)['capture_verified'])

    def test_word_width(self):self.assertFalse(parse_queue_watch(self.text().replace('x0=0','x0=100000000'),True)['capture_verified'])
    def test_ghost_prefix(self):self.assertFalse(parse_queue_watch(self.text().replace('status=captured','status=empty'),True)['capture_verified'])
    def test_ghost_headonly(self):self.assertFalse(parse_queue_watch(self.text().replace('status=captured','status=head-only'),True)['capture_verified'])
    def test_bare_frame(self):self.assertFalse(parse_queue_watch(self.text()+'QUEUE_WATCH_ENTRY',True)['capture_verified'])
    def test_conflicting_configuration(self):self.assertFalse(parse_queue_watch(self.text()+'TITLE_COUNTER_TRACE enabled=0',True)['capture_verified'])
    def test_no_sdk(self):self.assertFalse(parse_queue_watch(self.text().replace('TITLE_WAIT_SDK parent_attested=1',''),True)['capture_verified'])
    def test_unflagged(self):self.assertFalse(parse_queue_watch(self.text().replace('x0=0','x0=1'),True)['capture_verified'])

    def test_impossible_empty(self):self.assertFalse(parse_queue_watch(self.text().replace('status=captured','status=empty'),True)['capture_verified'])
    def test_invalid_manager(self):self.assertFalse(parse_queue_watch(self.text().replace('x7=40000000','x7=40000005'),True)['capture_verified'])
    def test_short_actual_bound(self):self.assertFalse(parse_queue_watch(self.text().replace('x3=40000004','x3=40000020'),True)['capture_verified'])

    def load(self, suffix='', missing=False):
        from tools.research.queue_watch_report import read_queue_watches
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            lines=self.text().splitlines()
            if not missing:Path(temp,'queue-watch-0.txt').write_text('\n'.join(lines[2:]))
            return read_queue_watches('\n'.join(lines[:2])+'\nQUEUE_WATCH_FILE reason=boundary path=queue-watch-0.txt success=1\n'+suffix,temp,True)[0]
    def test_load(self):self.assertTrue(self.load()['capture_verified'])
    def test_load_missing(self):self.assertFalse(self.load(missing=True)['capture_verified'])
    def test_load_later_failure(self):self.assertFalse(self.load('QUEUE_WATCH_FILE reason=fault path=queue-watch-1.txt success=0')['capture_verified'])
    def test_load_duplicate(self):self.assertFalse(self.load('QUEUE_WATCH_FILE reason=boundary path=queue-watch-0.txt success=1')['capture_verified'])
    def test_load_bad_declaration(self):self.assertFalse(self.load('QUEUE_WATCH_FILE')['capture_verified'])

    def test_unknown_namespace(self):self.assertFalse(parse_queue_watch(self.text()+'QUEUE_WATCH_BOGUS x=1',True)['capture_verified'])
    def test_bad_read_status(self):self.assertFalse(parse_queue_watch(self.text().replace('head_status=ok','head_status=banana'),True)['capture_verified'])
    def test_read_failure_retained(self):
        from pathlib import Path
        from unittest.mock import patch
        with patch.object(Path,'read_bytes',side_effect=OSError('retained failure')):
            self.assertFalse(self.load()['capture_verified'])

    def test_head_only_range_status(self):
        s=self.text().replace('status=captured','status=head-only').replace('flags=00001E9C','flags=0000029C').replace('table_captured=12','table_captured=0').replace('table_status=ok','table_status=outside-image').replace('table_hex=825C35088239973882399768','table_hex=')
        for k,v in [('x10','825C3508'),('x11','82399738'),('x12','82399768')]:s=s.replace(k+'='+v,k+'=0')
        self.assertFalse(parse_queue_watch(s,True)['capture_verified'])
