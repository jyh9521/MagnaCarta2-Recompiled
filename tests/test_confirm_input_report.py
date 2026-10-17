import tempfile,unittest
from pathlib import Path
import test_input_trace_report as fixture
PREFIX=fixture.PREFIX
from tools.research.input_trace_report import parse_input_trace,read_input_traces,parse_scripted_controller
class ConfirmReportTests(unittest.TestCase):
 def event(self):return fixture.InputReportTests.event(self).replace('START_EVENT','CONFIRM_EVENT').replace('key=5','key=A').replace('lr=827B4D10','lr=827B4DEC')
 def script(self):return fixture.ScriptedReportTests.text(self).replace('packet=3','packet=5').replace('last_tick=30100','last_tick=33100')+'TITLE_SCRIPTED_CONFIRM enabled=1 sdk_guard=1\nSCRIPTED_CONFIRM enabled=1 neutral_only=0 confirm_neutral=0 confirm_start_ms=32000 confirm_width_ms=500 confirm_polls=1 confirm_released_polls=1 a_key_down=0 a_key_up=0\n'
 def parse(self,s):return parse_scripted_controller(s,True,confirm_requested=True)
 def test_confirm_event(self):
  j=parse_input_trace(self.event(),'CONFIRM_EVENT',True);self.assertTrue(j['capture_verified'],j['errors']);self.assertEqual(len(j['transitions']),1);self.assertFalse(j['event_callback_verified'])
 def test_keyguard(self):self.assertFalse(parse_input_trace(self.event().replace('key=A','key=5'),'CONFIRM_EVENT',True)['capture_verified'])
 def test_lrguard(self):self.assertFalse(parse_input_trace(self.event().replace('827B4DEC','827B4D10'),'CONFIRM_EVENT',True)['capture_verified'])
 def test_address_guard(self):self.assertFalse(parse_input_trace(self.event().replace('obj=10000','obj=7EFFFF00'),'CONFIRM_EVENT',True)['capture_verified'])
 def test_userguard(self):self.assertFalse(parse_input_trace(self.event().replace('user=0','user=4'),'CONFIRM_EVENT',True)['capture_verified'])
 def test_pairguard(self):self.assertFalse(parse_input_trace(self.event().replace('tick_ms=25001','tick_ms=24000'),'CONFIRM_EVENT',True)['capture_verified'])
 def test_duplicate(self):self.assertFalse(parse_input_trace(self.event()+self.event(),'CONFIRM_EVENT',True)['capture_verified'])
 def test_state_A_BE(self):
  s=fixture.InputReportTests.state(self).replace('00000002001000000000000000000000','00000004100000000000000000000000');j=parse_input_trace(s,'INPUT_STATE',True);self.assertTrue(j['capture_verified']);self.assertEqual(j['entries'][0]['buttons'],0x1000);self.assertTrue(j['entries'][0]['confirm_pressed']);self.assertFalse(j['entries'][0]['start_pressed'])
 def test_confirm_script(self):self.assertTrue(self.parse(self.script())['capture_verified'])
 def test_disabled_confirm_rejects_record(self):self.assertFalse(parse_scripted_controller(self.script(),True)['capture_verified'])
 def test_missing_confirm_record(self):self.assertFalse(self.parse(self.script().split('SCRIPTED_CONFIRM enabled')[0])['capture_verified'])
 def test_duplicate_confirm_record(self):self.assertFalse(self.parse(self.script()+self.script().splitlines()[-1]+'\n')['capture_verified'])
 def test_confirm_packet(self):self.assertFalse(self.parse(self.script().replace('packet=5','packet=3'))['capture_verified'])
 def test_confirm_counter(self):self.assertFalse(self.parse(self.script().replace('confirm_polls=1','confirm_polls=100'))['capture_verified'])
 def test_confirm_release_counter(self):self.assertFalse(self.parse(self.script().replace('confirm_released_polls=1','confirm_released_polls=100'))['capture_verified'])
 def test_confirm_key_accounting(self):self.assertFalse(self.parse(self.script().replace('a_key_down=0','a_key_down=1'))['capture_verified'])
 def test_confirm_key_up(self):self.assertFalse(self.parse(self.script().replace('a_key_up=0','a_key_up=1'))['capture_verified'])
 def test_timing_guard(self):self.assertFalse(self.parse(self.script().replace('confirm_start_ms=32000','confirm_start_ms=30000'))['capture_verified'])
 def test_neutral_confirm(self):
  s=self.script().replace('neutral_only=0','neutral_only=1').replace('pressed_polls=1','pressed_polls=0').replace('released_polls=1','released_polls=0').replace('confirm_polls=1','confirm_polls=0').replace('packet=5','packet=1');self.assertTrue(self.parse(s)['capture_verified'])
 def test_neutral_confirm_pressed(self):self.assertFalse(self.parse(self.script().replace('neutral_only=0','neutral_only=1'))['capture_verified'])
 def test_missing_file(self):
  with tempfile.TemporaryDirectory()as d:self.assertFalse(read_input_traces(PREFIX+'CONFIRM_EVENT_FILE reason=boundary path=confirm-event-0.txt success=1\n',d,True,confirm_requested=True)['confirm_event']['capture_verified'])
 def test_declared_reader(self):
  with tempfile.TemporaryDirectory()as d:
   Path(d,'confirm-event-0.txt').write_text(self.event()[len(PREFIX):]);j=read_input_traces(PREFIX+'CONFIRM_EVENT_FILE reason=boundary path=confirm-event-0.txt success=1\n',d,True,confirm_requested=True);self.assertTrue(j['confirm_event']['capture_verified'],j['confirm_event']['errors'])

class ConfirmHostIntegrationTests(unittest.TestCase):
 def test_old_host_dependencies(self):
  from tools.research.probe_title_entry import input_observer_headers
  with tempfile.TemporaryDirectory()as d:
   p=Path(d,'host.cpp');p.write_text('#include "start_input_observation.h"');Path(d,'start_event_trace.h').write_text('// stage26 snapshot, no confirm adapter')
   headers,confirm=input_observer_headers(p);self.assertFalse(confirm);self.assertEqual(len(headers),4);self.assertNotIn('confirm_event_trace.h',[x.name for x in headers])
 def test_new_host_dependencies(self):
  from tools.research.probe_title_entry import input_observer_headers
  with tempfile.TemporaryDirectory()as d:
   p=Path(d,'host.cpp');p.write_text('#include "start_input_observation.h"');Path(d,'start_event_trace.h').write_text('#include "confirm_event_trace.h"')
   headers,confirm=input_observer_headers(p);self.assertTrue(confirm);self.assertEqual(headers[-1].name,'confirm_event_trace.h')
 def test_pre_input_host_dependencies(self):
  from tools.research.probe_title_entry import input_observer_headers
  with tempfile.TemporaryDirectory()as d:
   p=Path(d,'host.cpp');p.write_text('// stage25 host');self.assertEqual(input_observer_headers(p),([],False))
 def test_confirm_requires_scripted_start(self):
  from types import SimpleNamespace
  from tools.research.probe_title_entry import execute
  with self.assertRaisesRegex(ValueError,'requires the scripted START'):execute(SimpleNamespace(scripted_confirm=True,scripted_start=False))
 def test_false_mode_marker(self):
  s=fixture.ScriptedReportTests.text(self)+'TITLE_SCRIPTED_CONFIRM enabled=1 sdk_guard=1\n';self.assertFalse(parse_scripted_controller(s,True)['capture_verified'])
 def test_duplicate_false_mode_marker(self):
  s=fixture.ScriptedReportTests.text(self)+'TITLE_SCRIPTED_CONFIRM enabled=0 sdk_guard=1\n'*2;self.assertFalse(parse_scripted_controller(s,True)['capture_verified'])
 def test_real_start_only_mode_marker(self):
  s=fixture.ScriptedReportTests.text(self)+'TITLE_SCRIPTED_CONFIRM enabled=0 sdk_guard=1\n';self.assertTrue(parse_scripted_controller(s,True)['capture_verified'])

class ConfirmNeutralModeTests(unittest.TestCase):
 def script(self):return ConfirmReportTests.script(self).replace('confirm_neutral=0','confirm_neutral=1').replace('confirm_polls=1','confirm_polls=0').replace('confirm_released_polls=1','confirm_released_polls=0').replace('packet=5','packet=3')
 def test_same_caps_start_only(self):self.assertTrue(parse_scripted_controller(self.script(),True,True,True)['capture_verified'])
 def test_unrequested_control(self):self.assertFalse(parse_scripted_controller(self.script(),True,True,False)['capture_verified'])
 def test_control_with_A(self):self.assertFalse(parse_scripted_controller(self.script().replace('confirm_polls=0','confirm_polls=1'),True,True,True)['capture_verified'])
 def test_control_invalid_enum(self):self.assertFalse(parse_scripted_controller(self.script().replace('confirm_neutral=1','confirm_neutral=2'),True,True,True)['capture_verified'])
 def test_control_requires_confirm(self):
  from types import SimpleNamespace
  from tools.research.probe_title_entry import execute
  with self.assertRaisesRegex(ValueError,'requires confirmation mode'):execute(SimpleNamespace(scripted_confirm_neutral=True))
