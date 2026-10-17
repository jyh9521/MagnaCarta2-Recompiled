import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools.research.input_trace_report import parse_input_trace,read_input_traces,parse_scripted_controller
PREFIX='TITLE_WAIT_SDK parent_attested=1\nTITLE_INPUT_TRACE enabled=1 code_guard=1 binding_guard=1 configured=1\nINPUT_BIND target=82868178 dispatcher_hook=1 distinct_original=1\nINPUT_BIND target=827B4938 dispatcher_hook=1 distinct_original=1\n'
class InputReportTests(unittest.TestCase):
    def state(self):return PREFIX+'INPUT_STATE_TRACE status=frozen capacity=8192 reserved=1 calls=1 posts=1 dropped=0 suppressed=0 frozen=1 weak_snapshot=1\nINPUT_STATE_ENTRY slot=0 seq=1 call=1 thread=1 context=1234 lr=827B4C04 sp=20000 user=0 state_address=20000 status=0 tick_ms=25000 captured=16 read_status=ok hex=00000002001000000000000000000000\n'
    def event(self):
        head=PREFIX+'START_EVENT_TRACE status=frozen capacity=16384 reserved=2 calls=1 posts=1 selected=1 selected_posts=1 invalid_user=0 unknown=0 unwound=0 inflight=0 dropped=0 suppressed=0 frozen=1 weak_snapshot=1\n';rows=[]
        for i,phase,old in [(0,'pre','0'),(1,'post','FF')]:rows.append(f'START_EVENT_ENTRY slot={i} seq={i+1} call=1 phase={phase} thread=1 context=1234 lr=827B4D10 sp=20000 obj=10000 key=5 user=0 opaque=1234 new_value=FF old_known=1 old_word={old} old_status=ok tick_ms={25000+i} result=0')
        return head+'\n'.join(rows)+'\n'
    def bad(self,s,kind='INPUT_STATE'):self.assertFalse(parse_input_trace(s,kind,True)['capture_verified'])
    def test_state(self):
        j=parse_input_trace(self.state(),'INPUT_STATE',True);self.assertTrue(j['capture_verified'],j['errors']);self.assertEqual(j['entries'][0]['packet_number'],2);self.assertEqual(j['entries'][0]['buttons'],16)
    def test_event(self):
        j=parse_input_trace(self.event(),'START_EVENT',True);self.assertTrue(j['capture_verified'],j['errors']);self.assertEqual(len(j['transitions']),1)
    def test_disabled(self):self.assertEqual(parse_input_trace('')['status'],'disabled')
    def test_no_callback_claim(self):self.assertFalse(parse_input_trace(self.event(),'START_EVENT',True)['event_callback_verified'])
    def test_guard(self):self.bad(self.state().replace('code_guard=1','code_guard=0'))
    def test_binding(self):self.bad(self.state().replace('distinct_original=1','distinct_original=0',1))
    def test_truncated(self):self.bad(self.state().split('INPUT_STATE_ENTRY')[0])
    def test_bare(self):self.bad(self.state()+'INPUT_STATE_ENTRY')
    def test_unknown(self):self.bad(self.state()+'INPUT_STATE_BOGUS x=1')
    def test_duplicate(self):self.bad(self.state()+self.state().splitlines()[-1])
    def test_bad_bytes(self):self.bad(self.state().replace('hex=00000002001000000000000000000000','hex=00'))
    def test_error_cannot_have_bytes(self):self.bad(self.state().replace('status=0 tick','status=48F tick'))
    def test_error_without_read(self):
        s=self.state().replace('status=0 tick','status=48F tick').replace('captured=16 read_status=ok hex=00000002001000000000000000000000','captured=0 read_status=not-read-status hex=-');self.assertTrue(parse_input_trace(s,'INPUT_STATE',True)['capture_verified'])
    def test_image_address_rejected(self):self.bad(self.state().replace('state_address=20000','state_address=82000000'))
    def test_fake_known_word_address(self):self.bad(self.event().replace('obj=10000','obj=7FC80000'),'START_EVENT')
    def test_bad_consumer_user(self):self.bad(self.event().replace('user=0','user=4'),'START_EVENT')
    def test_bad_consumer_lr(self):self.bad(self.event().replace('lr=827B4D10','lr=827B4D14'),'START_EVENT')
    def test_bad_consumer_pair(self):self.bad(self.event().replace('old_word=FF old_status=ok tick_ms=25001','old_word=FF old_status=ok tick_ms=24999'),'START_EVENT')
    def test_counter_underflow(self):self.bad(self.state().replace('calls=1','calls=0'))
    def test_pending(self):
        s=self.event().rsplit('START_EVENT_ENTRY',1)[0]+'START_EVENT_PENDING slot=1\n';j=parse_input_trace(s,'START_EVENT',True);self.assertTrue(j['capture_verified']);self.assertFalse(j['storage_complete'])
    def test_suppressed_partial(self):self.assertFalse(parse_input_trace(self.state().replace('suppressed=0','suppressed=1'),'INPUT_STATE',True)['storage_complete'])
    def load(self,suffix='',missing=False):
        with tempfile.TemporaryDirectory()as d:
            for kind,stem,text in [('INPUT_STATE','input-state',self.state()),('START_EVENT','start-event',self.event())]:
                if not missing:Path(d,stem+'-0.txt').write_text(text[len(PREFIX):])
            run=PREFIX+'INPUT_STATE_FILE reason=boundary path=input-state-0.txt success=1\nSTART_EVENT_FILE reason=boundary path=start-event-0.txt success=1\n'+suffix
            return read_input_traces(run,d,True)
    def test_reader(self):self.assertTrue(all(self.load()[k]['capture_verified']for k in ['input_state','start_event']))
    def test_missing_files(self):self.assertFalse(self.load(missing=True)['input_state']['capture_verified'])
    def test_later_file_failure(self):self.assertFalse(self.load('INPUT_STATE_FILE reason=fault path=input-state-1.txt success=0')['input_state']['capture_verified'])
    def test_no_file_provenance(self):
        with tempfile.TemporaryDirectory()as d:self.assertFalse(read_input_traces(self.state(),d,True)['input_state']['capture_verified'])
    def test_read_error(self):
        with patch.object(Path,'read_bytes',side_effect=OSError('retained')):self.assertFalse(self.load()['input_state']['capture_verified'])

class ScriptedReportTests(unittest.TestCase):
    def text(self):return 'TITLE_SCRIPTED_START enabled=1 input_source=synthetic armed=1 sdk_guard=1 neutral_only=0\nSCRIPTED_CONTROLLER_SETUP status=00000000 input_source=synthetic setup_before_add=1 default_drivers_retained=1\nSCRIPTED_CONTROLLER input_source=synthetic automatic_only=1 physical_verified=0 made=1 setup=1 armed=1 neutral_only=0 device=5343524950540001 pulse_start_ms=25000 pulse_width_ms=500 arm_tick=100 polls=20 pressed_polls=1 released_polls=1 packet=3 first_tick=200 last_tick=30100 capabilities=0 keystroke_polls=0 key_down=0 key_up=0 empty=0 vibration=0 left=0 right=0 errors=0 setup_calls=1\n'
    def test_valid(self):self.assertTrue(parse_scripted_controller(self.text(),True)['capture_verified'])
    def test_no_physical_claim(self):self.assertFalse(parse_scripted_controller(self.text(),True)['physical_input_verified'])
    def test_disabled(self):self.assertEqual(parse_scripted_controller('')['status'],'disabled')
    def test_wrong_physical(self):self.assertFalse(parse_scripted_controller(self.text().replace('physical_verified=0','physical_verified=1'),True)['capture_verified'])
    def test_missing_setup(self):self.assertFalse(parse_scripted_controller(self.text().replace('setup_before_add=1','setup_before_add=0'),True)['capture_verified'])
    def test_bad_counter(self):self.assertFalse(parse_scripted_controller(self.text().replace('pressed_polls=1','pressed_polls=99'),True)['capture_verified'])
    def test_neutral(self):
        s=self.text().replace('neutral_only=0','neutral_only=1').replace('pressed_polls=1','pressed_polls=0').replace('released_polls=1','released_polls=0').replace('packet=3','packet=1');self.assertTrue(parse_scripted_controller(s,True)['capture_verified'])
    def test_neutral_with_press(self):self.assertFalse(parse_scripted_controller(self.text().replace('neutral_only=0','neutral_only=1'),True)['capture_verified'])
    def test_duplicate(self):self.assertFalse(parse_scripted_controller(self.text()+self.text(),True)['capture_verified'])

class InputSequenceBoundsTests(unittest.TestCase):
    state=InputReportTests.state
    bad=InputReportTests.bad
    def test_future_call(self):self.bad(self.state().replace('call=1 thread','call=999999 thread'))
    def test_future_sequence(self):self.bad(self.state().replace('seq=1','seq=999999'))

class DriverSnapshotBoundsTests(unittest.TestCase):
    text=ScriptedReportTests.text
    def test_keystroke_accounting(self):self.assertFalse(parse_scripted_controller(self.text().replace('keystroke_polls=0','keystroke_polls=3'),True)['capture_verified'])
    def test_packet_accounting(self):self.assertFalse(parse_scripted_controller(self.text().replace('pressed_polls=1','pressed_polls=0').replace('released_polls=1','released_polls=0'),True)['capture_verified'])
    def test_vibration_accounting(self):self.assertFalse(parse_scripted_controller(self.text().replace('left=0','left=1'),True)['capture_verified'])
