"""Portable fail-closed report contracts; not substitutes for the real title run."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.research import probe_title_entry as p
from tools.research.link_module import title_thread_resumed

MAP=''' Preferred load address is 0000000140000000
 0001:00001000 xstart 0000000140002000 f game.obj
 0001:00002000 sub_82E1F578 0000000140003000 f game.obj
 0001:00003000 sub_82944420 0000000140004000 f game.obj
'''
RUN='''TITLE_LOAD status=00000000
TITLE_RESUMED status=00000000
TITLE_EXCEPTION code=C0000005 ip=0000000140004010 phase=2 thread=3
TITLE_FAULT operation=0 address=0000000200000000 guest_offset=0000000000000000
TITLE_STACK 4 address=0000000140004010 rva=4010 module=C:\\probe\\module_probe.exe
TITLE_STACK 5 address=0000000140003004 rva=3004 module=C:\\probe\\module_probe.exe
TITLE_STACK 6 address=0000000140002004 rva=2004 module=C:\\probe\\module_probe.exe
TITLE_NATIVES guard=1 bound=4096 fallback=3794 int_const=82508E60 add=8250BAF0
'''


class TitleEntryTests(unittest.TestCase):
    def test_presentation_requires_every_positive_marker(self):
        lines=['PRESENTATION_CONTEXT initialized=1 ui_thread=1',
               'PRESENTATION_SETUP status=00000000 has_presentation=1 presenter=1',
               'PRESENTATION_WINDOW open=1 hidden=1 binding_requested=1',
               'TITLE_PRESENTATION bound_before_setup=1 hidden=1']
        self.assertTrue(p.presentation_observation('\n'.join(lines))['initialized'])
        for i in range(len(lines)):
            self.assertFalse(p.presentation_observation('\n'.join(lines[:i]+lines[i+1:]))['initialized'])
        self.assertFalse(p.presentation_observation('\n'.join(reversed(lines)))['initialized'])
        self.assertFalse(p.presentation_observation('\n'.join(lines+lines))['initialized'])
        r=p.presentation_observation('\n'.join(lines));self.assertFalse(r['visible_frame_verified'])
        self.assertFalse(r['title_shutdown_verified']);self.assertFalse(r['loop_entered'])

    def test_wait_object_metadata_retains_unknown_not_signaled_false(self):
        text='TITLE_WAIT_OBJECT sample=0 handle=F80000AC status=observed type_name=event event_signal_known=0 scope=public-readonly\n'
        r=p.wait_observations(text)[0]
        self.assertEqual(r['event_signal_known'],'0');self.assertNotIn('event_signal',r)
        self.assertEqual(r['handle'],'F80000AC');self.assertEqual(r['type_name'],'event')
        self.assertEqual(p.wait_observations(text.replace('public-readonly','other')),[])
        self.assertEqual(p.wait_observations('TITLE_WAIT_OBJECT incomplete'),[])

    def test_sdk_wait_attestation_matches_header_contract(self):
        text=Path('src/host/wait_observation.h').read_text(encoding='utf-8')
        self.assertIn(p.WAIT_SDK_SHA256,text)
        self.assertEqual(len(p.WAIT_SDK_SHA256),64)

    def test_presentation_requires_gpu_before_any_input_read(self):
        from types import SimpleNamespace
        with self.assertRaisesRegex(ValueError,'requires the real GPU'):
            p.execute(SimpleNamespace(present=True,gpu=False))

    def test_bulk_resolver_matches_single_lookup(self):
        symbols=p.map_symbols(MAP);lookup=p.make_symbol_resolver(symbols)
        for address in (0,0x2000,0x2004,0x3010,0xFFFF):
            self.assertEqual(lookup(address),p.resolve_rva(symbols,address))

    def test_observation_range_checked_before_inputs(self):
        from types import SimpleNamespace
        for seconds in (19,61):
            with self.assertRaisesRegex(ValueError,'20..60'):
                p.execute(SimpleNamespace(observe_seconds=seconds))

    def test_sdk_guest_fault_overrides_bounded_wait_marker(self):
        r=self.observation(sdk='Unhandled guest access violation: write of guest 0x00000003 (host 0x100000003)')
        self.assertFalse(r['bounded_observation']);self.assertEqual(r['sdk_guest_faults'][0]['guest_address'],3)

    def test_float_fp_contract(self):
        p.validate_fp_contract('float-leaf-82AC1DE8',{'floating_point_contract':'strict'},[{'command':['clang-cl','/fp:strict']}])
        for inputs,rows in [({},[]),({'floating_point_contract':'strict'},[]),({'floating_point_contract':'strict'},[{'command':['/fp:precise']}]),({'floating_point_contract':'strict'},[{'command':['/fp:strict','/fp:fast']}])]:
            with self.assertRaises(ValueError):p.validate_fp_contract('float-leaf-82AC1DE8',inputs,rows)

    def test_old_fp_contract_rollback(self):
        p.validate_fp_contract('extended-native-event-trace-rebuild',{},[])

    def test_float_leaf_profile_exact(self):
        self.assertEqual(p.validate_title_profile({'tree_sha256':p.FLOAT_LEAF_GENERATED_TREE}),'float-leaf-82AC1DE8')

    def test_event_trace_rebuild_profile_exact(self):
        self.assertEqual(p.validate_title_profile({'tree_sha256':p.EVENT_TRACE_REBUILD_TREE}),'extended-native-event-trace-rebuild')

    def test_rebuilt_extended_native_profile_exact(self):
        self.assertEqual(p.validate_title_profile({'tree_sha256':p.PRESENTATION_REBUILD_TREE}),'extended-native-presentation-rebuild')

    def test_extended_native_profile(self):
        self.assertEqual(p.validate_title_profile({'tree_sha256':p.EXTENDED_NATIVE_GENERATED_TREE}),'extended-native-82517D70')

    def observation(self,exit=26,sdk=''):
        text='TITLE_LOAD status=00000000\nTITLE_RESUMED status=00000000\nTITLE_WAIT result=2 running=1\n'
        for i in range(3):
            text+=f'TITLE_SAMPLE sample={i} pc=140002004 lr=82869BC0 ctr=8248B100\n'
            text+=f'TITLE_SAMPLE_STACK sample={i} index=0 address=140002004 rva=2004 module=C:\\probe\\module_probe.exe\n'
        return p.analyze(text,sdk,p.map_symbols(MAP),exit)

    def test_bounded_observation_is_not_located_blocker_or_boot(self):
        r=self.observation(sdk='IssueSwap: presenter is null\n'*2)
        self.assertTrue(r['bounded_observation']);self.assertFalse(r['diagnostic_success'])
        self.assertFalse(r['game_boot_success']);self.assertFalse(r['shutdown_verified'])
        self.assertEqual(r['presenter_null_reports'],2)
        self.assertIn('not proof of deadlock',r['blocker_classification'])

    def test_missing_probe_without_fault_does_not_claim_fault(self):
        r=self.observation(sdk="[NtCreateFile] FAILED: path='optional' -> 0xc000000f")
        self.assertTrue(r['bounded_observation'])
        self.assertNotIn('precede fault',r['blocker_classification'])
        r=p.analyze('',"[NtCreateFile] FAILED: path='optional' -> 0xc000000f",[],1)
        self.assertFalse(r['bounded_observation']);self.assertEqual(r['blocker_classification'],'no positively located blocker')

    def test_process_timeout_cannot_be_bounded_observation(self):
        r=self.observation(exit=124);self.assertFalse(r['bounded_observation'])
        self.assertTrue(r['timed_out'])

    def test_native_gateway_profile(self):
        self.assertEqual(p.validate_title_profile({'tree_sha256':p.NATIVE_GATEWAY_GENERATED_TREE}),'native-gateway-82509380')

    def test_compare_profile(self):
        self.assertEqual(p.validate_title_profile({'tree_sha256':p.COMPARE_GENERATED_TREE}),'compare-callback-82C1C1A0')

    def test_virtual_thunk_profile(self):
        self.assertEqual(p.validate_title_profile({'tree_sha256':p.VIRTUAL_THUNK_GENERATED_TREE}),'virtual-thunk-823C2740')

    def test_callback_profile(self):
        self.assertEqual(p.validate_title_profile({'tree_sha256':p.CALLBACK_GENERATED_TREE}),'callback-entry-8234FF10')

    def test_original_profile_preserved(self):
        self.assertEqual(p.validate_title_profile({'tree_sha256':p.link_module.NATIVE_GENERATED_TREE}),'phase5-missing-callback-baseline')

    def test_unknown_title_profile_rejected(self):
        for value in ({},{'tree_sha256':'unknown'}):
            with self.assertRaises(ValueError):p.validate_title_profile(value)

    def test_map_aslr_independent_rva(self):
        self.assertEqual(p.resolve_rva(p.map_symbols(MAP),0x4010)['name'],'sub_82944420')
        self.assertEqual(p.resolve_rva(p.map_symbols(MAP),0x4010)['offset'],16)

    def test_map_requires_base(self):
        with self.assertRaisesRegex(ValueError,'preferred'):p.map_symbols('no map')

    def test_map_requires_symbols(self):
        with self.assertRaisesRegex(ValueError,'symbols'):p.map_symbols('Preferred load address is 140000000')

    def test_rva_before_symbols_unresolved(self):
        self.assertIsNone(p.resolve_rva(p.map_symbols(MAP),1))

    def test_actual_markers_and_stack_locate_fault_not_boot(self):
        result=p.analyze(RUN,'',p.map_symbols(MAP),3221225477)
        self.assertTrue(result['diagnostic_success'])
        self.assertTrue(result['original_entry_execution_observed'])
        self.assertTrue(result['main_candidate_observed'])
        self.assertFalse(result['game_boot_success'])
        self.assertEqual(result['natives']['fallback'],3794)
        self.assertEqual(result['fault_memory']['guest_offset'],0)

    def test_timeout_is_not_a_location_even_with_partial_exception(self):
        result=p.analyze(RUN,'',p.map_symbols(MAP),124)
        self.assertTrue(result['timed_out'])
        self.assertFalse(result['diagnostic_success'])

    def test_resume_alone_is_not_execution_evidence(self):
        result=p.analyze('TITLE_RESUMED status=00000000\n','',[],1)
        self.assertFalse(result['original_entry_execution_observed'])
        self.assertFalse(result['diagnostic_success'])

    def test_missing_assets_not_runtime_defect(self):
        result=p.analyze(RUN,"[NtCreateFile] FAILED: path='D:\\MC2Game\\Xbox360TOC.txt' -> 0xc000000f",p.map_symbols(MAP),3221225477)
        self.assertIn('environment',result['blocker_classification'])
        self.assertEqual(result['failed_file_operations'][0]['status'],'0xc000000f')

    def test_host_null_not_mislabeled_guest_address(self):
        result=p.analyze(RUN.replace('guest_offset=0000000000000000','guest_offset=FFFFFFFF0000004C'),'',p.map_symbols(MAP),1)
        self.assertIsNone(result['fault_memory']['guest_offset'])

    def test_same_xex_required_in_actual_mounted_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir();mounted=root/'mounted';mounted.mkdir()
            image=source/'default.xex';image.write_bytes(b'synthetic')
            with patch.object(p,'digest',return_value=p.XEX_SHA256):
                with self.assertRaisesRegex(ValueError,'same verified'):p.validate_image(image,mounted)
                (mounted/'default.xex').write_bytes(b'synthetic')
                self.assertEqual(p.validate_image(image,mounted)['mounted'],str((mounted/'default.xex').resolve()))

    def test_unknown_image_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            image=Path(directory)/'image.xex';image.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'verified disc-1'):p.validate_image(image,image.parent)

    def test_resume_marker_is_exact(self):
        self.assertTrue(title_thread_resumed('TITLE_RESUMED status=00000000\n'))
        for text in ('TITLE_RESUMED status=C0000001','prefix TITLE_RESUMED status=00000000',''):
            self.assertFalse(title_thread_resumed(text))

    def test_sample_stack_is_observation_not_automatic_blocker(self):
        text='TITLE_LOAD status=00000000\nTITLE_RESUMED status=00000000\n'
        for i in range(3):
            text+=f'TITLE_SAMPLE sample={i} pc=0000000140004010 r1=70000000 r3=00000001 lr=82368EE0 ctr=00000000\n'
            text+=f'TITLE_SAMPLE_STACK sample={i} index=0 address=0000000140002004 rva=2004 module=C:\\probe\\module_probe.exe\n'
            text+=f'TITLE_RING sample={i} object=40000000 read_address=FFC9B000 read=00000000 write=0000000F flags=04\n'
        result=p.analyze(text,'',p.map_symbols(MAP),26)
        self.assertTrue(result['stack_sample_observed'])
        self.assertTrue(result['original_entry_execution_observed'])
        self.assertFalse(result['diagnostic_success'])
        self.assertEqual(len(result['ring_samples']),3)
        self.assertEqual(result['ring_samples'][2]['write'],15)

    def test_load_failure_does_not_claim_entry(self):
        result=p.analyze(RUN.replace('TITLE_LOAD status=00000000','TITLE_LOAD status=C0000001'),'',p.map_symbols(MAP),1)
        self.assertFalse(result['image_loaded'])
        self.assertFalse(result['original_entry_execution_observed'])
        self.assertFalse(result['diagnostic_success'])

    def test_sdk_fatal_and_observed_callstack_locate_dispatch_gap(self):
        fatal='Call to invalid or unregistered function at guest address 0x8234FF10'
        text='TITLE_LOAD status=00000000\nTITLE_RESUMED status=00000000\n'
        text+='TITLE_FATAL [FATAL] '+fatal+'\n'
        text+='TITLE_FATAL_STACK sample=0 index=0 address=0000000140002004 rva=2004 module=C:\\probe\\module_probe.exe\n'
        result=p.analyze(text,'[critical] [FATAL] '+fatal,p.map_symbols(MAP),3221226505)
        self.assertTrue(result['diagnostic_success'])
        self.assertTrue(result['sdk_fatal_corroborated'])
        self.assertTrue(result['original_entry_execution_observed'])
        self.assertEqual(result['unregistered_guest_target'],0x8234FF10)
        self.assertFalse(result['game_boot_success'])
        self.assertFalse(result['shutdown_verified'])

    def test_fatal_without_stack_or_sdk_log_not_located(self):
        text='TITLE_LOAD status=00000000\nTITLE_RESUMED status=00000000\n'
        text+='TITLE_FATAL [FATAL] Call to invalid or unregistered function at guest address 0x8234FF10\n'
        self.assertFalse(p.analyze(text,'',p.map_symbols(MAP),3221226505)['diagnostic_success'])

    def test_internal_wait_window_distinct_from_process_timeout(self):
        result=p.analyze('TITLE_WAIT result=2 running=1\n','',[],26)
        self.assertTrue(result['observation_window_elapsed'])
        self.assertFalse(result['timed_out'])

    def test_changed_runtime_asset_rejects_diagnostic(self):
        result={'inputs_unchanged':True,'runtime_dll_verified':True,'runtime_assets_unchanged':False}
        report={'game_input_unchanged':True,'gpu_plugin_path_verified':True}
        self.assertFalse(p.diagnostic_input_guards(result,report))
        result['runtime_assets_unchanged']=True
        self.assertTrue(p.diagnostic_input_guards(result,report))

    def test_legacy_no_runtime_assets_guard_defaults_true(self):
        self.assertTrue(p.diagnostic_input_guards({'inputs_unchanged':True,'runtime_dll_verified':True},
            {'game_input_unchanged':True,'gpu_plugin_path_verified':True}))


if __name__=='__main__':unittest.main()
