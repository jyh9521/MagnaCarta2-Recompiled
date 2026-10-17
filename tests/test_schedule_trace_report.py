import unittest
from tools.research.schedule_trace_report import parse_schedule_trace

PREFIX='TITLE_WAIT_SDK parent_attested=1\nTITLE_SCHEDULE_TRACE installed=1 code_guard=1\nTITLE_SCHEDULE_TRACE restored=1\n'
HEAD='SCHEDULE_TRACE status=restored keys=192 bins=128 bucket_ms=500 calls=2 key_overflow=0 late=0 frozen=1 weak_snapshot=1 elapsed_ms=1000\n'
KEY='SCHEDULE_KEY key=0 api=__imp__KeDelayExecutionThread thread=7 lr=82869854 a0=1 a1=0 a2=70180050 pre=1 post=1 sampled=1\n'
def entry(phase):
 return f'SCHEDULE_ENTRY key=0 bin=1 phase={phase} call=1 tick_ms=501 thread=7 context=400000000 lr=82869854 sp=70180000 r3=1 r4=0 r5=70180050 r6=0 r7=0 r8=0 r9=0 r10=0 result=0 r29=0 r30=0 r31=0 flags=0000003F x0=0 x1=823997AC x2=40001000 x3=1 x4=2 x5=40002000 x6=0 x7=0\n'
API=''.join(f'SCHEDULE_API api={a} pre={n} post={n} key_overflow=0\n' for a,n in [('__imp__KeDelayExecutionThread',1),('__imp__RtlEnterCriticalSection',0),('__imp__RtlLeaveCriticalSection',0)])
def fixture():return PREFIX+HEAD+API+KEY+entry('pre')+entry('post')
class ScheduleReportTests(unittest.TestCase):
 def test_disabled(self):self.assertEqual(parse_schedule_trace('')['status'],'disabled')
 def test_absence_is_failure_when_requested(self):self.assertFalse(parse_schedule_trace('',True)['capture_verified'])
 def test_valid_poll(self):
  r=parse_schedule_trace(fixture(),True);self.assertTrue(r['capture_verified'],r['errors']);self.assertEqual(r['poll_samples'][0]['counter'],2);self.assertEqual(r['poll_samples'][0]['threshold'],1);self.assertTrue(r['poll_samples'][0]['condition_gt']);self.assertFalse(r['deadlock_verified'])
 def test_wrong_code_guard(self):self.assertFalse(parse_schedule_trace(fixture().replace('code_guard=1','code_guard=0'),True)['capture_verified'])
 def test_wrong_sdk(self):self.assertFalse(parse_schedule_trace(fixture().replace('parent_attested=1','parent_attested=0'),True)['capture_verified'])
 def test_pair_mismatch(self):self.assertFalse(parse_schedule_trace(fixture().replace('phase=post call=1','phase=post call=2'),True)['capture_verified'])
 def test_duplicate_entry(self):self.assertFalse(parse_schedule_trace(fixture()+entry('pre'),True)['capture_verified'])
 def test_bad_bin(self):self.assertFalse(parse_schedule_trace(fixture().replace('bin=1','bin=129'),True)['capture_verified'])
 def test_duplicate_header(self):self.assertFalse(parse_schedule_trace(fixture()+HEAD,True)['capture_verified'])
 def test_missing_frame_read_not_poll_proof(self):self.assertEqual(parse_schedule_trace(fixture().replace('flags=0000003F','flags=00000001'),True)['poll_samples'],[])
 def test_hook_exception(self):self.assertFalse(parse_schedule_trace(fixture().replace('flags=0000003F','flags=80000000'),True)['capture_verified'])
 def test_pending_post_not_deadlock(self):
  t=PREFIX+HEAD+API+KEY+entry('pre')+'SCHEDULE_PENDING key=0 bin=1 phase=post\n';r=parse_schedule_trace(t,True);self.assertTrue(r['capture_verified']);self.assertEqual(len(r['pending']),1);self.assertFalse(r['deadlock_verified'])
 def test_overflow_explicit_not_silent_completion(self):
  r=parse_schedule_trace(fixture().replace('key_overflow=0','key_overflow=9'),True);self.assertTrue(r['capture_verified']);self.assertFalse(r['coverage_complete']);self.assertEqual(r['counters']['key_overflow'],9)
 def test_wrong_caller_not_poll_proof(self):self.assertEqual(parse_schedule_trace(fixture().replace('x1=823997AC','x1=823997A0'),True)['poll_samples'],[])
 def test_suspicious_unknown_line(self):self.assertFalse(parse_schedule_trace(fixture()+'SCHEDULE_ENTRY broken\n',True)['capture_verified'])
 def test_contradictory_sdk_marker(self):self.assertFalse(parse_schedule_trace(fixture()+'TITLE_WAIT_SDK parent_attested=0\n',True)['capture_verified'])
 def test_contradictory_install_marker(self):self.assertFalse(parse_schedule_trace(fixture()+'TITLE_SCHEDULE_TRACE installed=0 code_guard=0\n',True)['capture_verified'])
 def test_contradictory_restore_marker(self):self.assertFalse(parse_schedule_trace(fixture()+'TITLE_SCHEDULE_TRACE restored=0\n',True)['capture_verified'])
 def test_verified_parent_lr(self):
  r=parse_schedule_trace(fixture().replace('flags=0000003F','flags=000000BF').replace('x7=0','x7=82E2080C'),True);self.assertTrue(r['capture_verified']);self.assertEqual(r['poll_samples'][0]['parent_lr'],0x82E2080C)
 def test_truncated_all_claimed_samples(self):
  t=fixture().replace(entry('pre'),'').replace(entry('post'),'');self.assertFalse(parse_schedule_trace(t,True)['capture_verified'])
 def test_unreported_claimed_bin(self):self.assertFalse(parse_schedule_trace(fixture().replace('pre=1 post=1 sampled=1','pre=2 post=2 sampled=2'),True)['capture_verified'])
 def test_flags_uint32_only(self):self.assertFalse(parse_schedule_trace(fixture().replace('flags=0000003F','flags=10000003F'),True)['capture_verified'])
 def test_unknown_extra_flag_bits(self):self.assertFalse(parse_schedule_trace(fixture().replace('flags=0000003F','flags=0000013F'),True)['capture_verified'])
 def test_pair_immutable_args(self):
  t=fixture().replace(entry('post'),entry('post').replace('r6=0','r6=1'));self.assertFalse(parse_schedule_trace(t,True)['capture_verified'])
