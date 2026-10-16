"""Synthetic fail-closed trace framing, not original game execution."""
import unittest
from tools.research.event_trace_report import parse_event_trace,correlate_handle


def row(slot,call,phase,api='__imp__NtCreateEvent',out=False):
    r3='F80000AC' if api=='__imp__NtWaitForSingleObjectEx' else '2000'
    args=' '.join(f'r{i}={r3 if i==3 else "0"}' for i in range(3,11))
    return f'EVENT_TRACE_ENTRY slot={slot} call={call} phase={phase} api={api} thread=12 context=20 lr=82869BC0 sp=1000 {args} result={"0" if phase=="post" else r3} out_read={int(out)} out_handle={"F80000AC" if out else "00000000"}'


def trace(extra='',pending=False):
    n=4 if pending else 3
    return '\n'.join(['TITLE_EVENT_TRACE installed=1','TITLE_EVENT_TRACE restored=1',
        'TITLE_MAIN_THREAD host=12 context=20 guest=6',
        f'EVENT_TRACE status=restored capacity=8192 reserved={n} dropped=0 reset_export=absent frozen=1 weak_snapshot=1 cutoff={n}',
        'EVENT_TRACE_MODULE base=140000000 size=10000',row(0,0,'pre'),row(1,0,'post',out=True),
        row(2,1,'pre','__imp__NtWaitForSingleObjectEx'),
        'EVENT_TRACE_PENDING slot=3' if pending else '',extra])


class EventTraceReportTests(unittest.TestCase):
    def test_complete_and_numeric_correlation(self):
        result=parse_event_trace(trace());self.assertTrue(result['capture_verified'],result['errors'])
        self.assertEqual(result['calls_without_post'],[1])
        r=correlate_handle(result,0xF80000AC)
        self.assertEqual(len(r['create_candidates']),1);self.assertEqual(len(r['wait_pre']),1)
        self.assertEqual(r['set_pre'],[]);self.assertNotIn('signal_state',r)
        self.assertIn('reuse',r['limits'])

    def test_partial_pending_is_not_complete(self):
        result=parse_event_trace(trace(pending=True));self.assertFalse(result['capture_verified'])
        self.assertEqual(result['errors'],[]);self.assertEqual(result['pending_slots'],[3])

    def test_duplicate_slot_and_call_phase_rejected(self):
        for text in (trace().replace('slot=1 call=0','slot=0 call=0'),trace().replace('phase=post','phase=pre')):
            r=parse_event_trace(text);self.assertFalse(r['capture_verified']);self.assertTrue(r['errors'])

    def test_wrong_api_or_post_identity_rejected(self):
        for text in (trace().replace('__imp__NtCreateEvent','__imp__NtResetEvent'),trace().replace('slot=1 call=0 phase=post api=__imp__NtCreateEvent thread=12','slot=1 call=0 phase=post api=__imp__NtCreateEvent thread=13')):
            r=parse_event_trace(text);self.assertFalse(r['capture_verified']);self.assertTrue(r['errors'])

    def test_out_handle_requires_successful_create_post(self):
        for text in (trace().replace('result=0 out_read=1','result=C0000001 out_read=1'),trace().replace('out_read=1','out_read=2')):
            r=parse_event_trace(text);self.assertFalse(r['capture_verified']);self.assertTrue(r['errors'])

    def test_frame_module_identity_and_resolution(self):
        line='EVENT_TRACE_FRAME slot=0 index=0 address=140002004 module=own rva=2004'
        result=parse_event_trace(trace(line),lambda rva:{'rva':rva})
        self.assertTrue(result['capture_verified']);self.assertEqual(result['frames'][0]['nearest_symbol'],{'rva':0x2004})
        result=parse_event_trace(trace(line.replace('address=140002004','address=150002004')))
        self.assertFalse(result['capture_verified']);self.assertTrue(result['errors'])
        self.assertFalse(parse_event_trace(trace(line+'\n'+line))['capture_verified'])

    def test_last_dump_only_and_main_thread_required(self):
        result=parse_event_trace('EVENT_TRACE status=broken\n'+trace());self.assertTrue(result['capture_verified'])
        result=parse_event_trace(trace().replace('TITLE_MAIN_THREAD host=12 context=20 guest=6',''))
        self.assertFalse(result['capture_verified']);self.assertTrue(result['errors'])

    def test_install_restore_and_drop_must_be_positive(self):
        for text in (trace().replace('installed=1','installed=0'),trace().replace('restored=1','restored=0'),trace().replace('dropped=0','dropped=1'),trace().replace('frozen=1','frozen=0')):
            self.assertFalse(parse_event_trace(text)['capture_verified'])
        self.assertFalse(parse_event_trace('')['capture_verified'])

    def test_incomplete_and_post_without_pre_fail_closed(self):
        for text in (trace().replace('r10=0',''),trace().replace('slot=1 call=0','slot=1 call=9'),trace().replace('cutoff=3','cutoff=2')):
            r=parse_event_trace(text);self.assertFalse(r['capture_verified']);self.assertTrue(r['errors'])


if __name__=='__main__':unittest.main()
