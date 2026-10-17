import unittest
from tools.research.counter_trace_report import parse_counter_trace
TARGETS=(0x82399650,0x82399738,0x822D0A68)
PREFIX='TITLE_WAIT_SDK parent_attested=1\nTITLE_COUNTER_TRACE enabled=1 code_guard=1 binding_guard=1 configured=1\nCOUNTER_INITIAL counter=83265218 word_known=1 value=00000000\n'+''.join(f'COUNTER_BIND target={t:08X} dispatcher_hook=1 distinct_original=1\n'for t in TARGETS)
HEAD='COUNTER_TRACE status=frozen capacity=8192 targets=3 total_capacity=24576 reserved=2 calls=1 posts=1 dropped=0 suppressed=0 frozen=1 weak_snapshot=1\n'
def target_rows():return ''.join(f'COUNTER_TARGET kind={k} target={t:08X} reserved={2 if k==0 else 0} pre={1 if k==0 else 0} post={1 if k==0 else 0} selected={1 if k==0 else 0} selected_post={1 if k==0 else 0} unknown=0 unknown_post=0 dropped=0 suppressed=0 frozen=1\n'for k,t in enumerate(TARGETS))
def entry(phase):
 slot=0 if phase=='pre' else 1;vals=[0x83265218,1 if phase=='pre' else 2,1]+[0]*17
 return f'COUNTER_ENTRY slot={slot} seq={slot+1} call=1 parent=0 target=82399650 phase={phase} thread=7 context=400000000 lr=82E20800 sp=70180000 r3=83265218 r4=0 r5=0 r6=0 r7=0 r8=0 r9=0 r10=0 result=0 selection=1 flags=00000007'+''.join(f' x{i}={v:X}'for i,v in enumerate(vals))+'\n'
def fixture():return PREFIX+HEAD+target_rows()+entry('pre')+entry('post')
class CounterTraceTests(unittest.TestCase):
 def test_default_disabled(self):self.assertEqual(parse_counter_trace('')['status'],'disabled')
 def test_missing_requested(self):self.assertFalse(parse_counter_trace('',True)['capture_verified'])
 def test_valid_increment(self):
  r=parse_counter_trace(fixture(),True);self.assertTrue(r['capture_verified'],r['errors']);self.assertEqual(r['increments'][0]['before'],1);self.assertEqual(r['increments'][0]['after'],2);self.assertFalse(r['complete_lifecycle_verified'])
 def test_bad_code_guard(self):self.assertFalse(parse_counter_trace(fixture().replace('code_guard=1','code_guard=0'),True)['capture_verified'])
 def test_bad_binding(self):self.assertFalse(parse_counter_trace(fixture().replace('dispatcher_hook=1','dispatcher_hook=0',1),True)['capture_verified'])
 def test_original_not_distinct(self):self.assertFalse(parse_counter_trace(fixture().replace('distinct_original=1','distinct_original=0',1),True)['capture_verified'])
 def test_sdk_contradiction(self):self.assertFalse(parse_counter_trace(fixture()+'TITLE_WAIT_SDK parent_attested=0\n',True)['capture_verified'])
 def test_all_samples_truncated(self):self.assertFalse(parse_counter_trace(PREFIX+HEAD+target_rows(),True)['capture_verified'])
 def test_one_slot_truncated(self):self.assertFalse(parse_counter_trace(fixture().replace(entry('post'),''),True)['capture_verified'])
 def test_duplicate_slot(self):self.assertFalse(parse_counter_trace(fixture()+entry('pre'),True)['capture_verified'])
 def test_flags_unknown_bits(self):self.assertFalse(parse_counter_trace(fixture().replace('flags=00000007','flags=00100007'),True)['capture_verified'])
 def test_flags_overflow(self):self.assertFalse(parse_counter_trace(fixture().replace('flags=00000007','flags=100000007'),True)['capture_verified'])
 def test_pair_immutable_arguments(self):self.assertFalse(parse_counter_trace(fixture().replace(entry('post'),entry('post').replace('r4=0','r4=1')),True)['capture_verified'])
 def test_phase_pair_call_mismatch(self):self.assertFalse(parse_counter_trace(fixture().replace('seq=2 call=1','seq=2 call=2'),True)['capture_verified'])
 def test_header_duplicate(self):self.assertFalse(parse_counter_trace(fixture()+HEAD,True)['capture_verified'])
 def test_pending_slot_explicit(self):
  r=parse_counter_trace(fixture().replace(entry('post'),'COUNTER_PENDING slot=1\n'),True);self.assertTrue(r['capture_verified']);self.assertFalse(r['storage_complete']);self.assertFalse(r['complete_lifecycle_verified'])
 def test_unknown_observation_not_absence_proof(self):
  r=parse_counter_trace(fixture().replace('selected=0 selected_post=0 unknown=0','selected=0 selected_post=0 unknown=1',1),True);self.assertTrue(r['capture_verified']);self.assertFalse(r['storage_complete'])
 def test_initial_value_not_assumed(self):
  r=parse_counter_trace(fixture().replace('value=00000000','value=00000003'),True);self.assertTrue(r['capture_verified']);self.assertEqual(r['initial_counter'],3)
