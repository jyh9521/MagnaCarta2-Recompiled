import copy
import unittest
from tools.research.deployment_evidence import compare_roots,summarize_trials

MEMBER='MC2Game/CookedXenon/sample.xxx'
H='a'*64
J='b'*64


def inv(files):return {'files':files}


def utfrow(text, guest):
    raw=(text+'\0').encode('utf-16be').hex().upper()
    return {'guest':guest,'status':'ok','captured':len(raw)//2,'terminated':True,
            'truncated':False,'word_known':False,'word':0,'hex':raw,'text':text}


def report(kind='target'):
    # Mirrors typed output fields from actual probe_title_entry/analyze + parser.
    value={'inputs_unchanged':True,'game_input_unchanged':True,'image_loaded':True,
           'guest_entrypoint_launched':True,'diagnostic_success':True,'timed_out':False}
    if kind in ('target','other'):
        filename='..\\'+(MEMBER if kind=='target' else 'MC2Game/other.xxx').replace('/','\\')
        value.update(exit_status=3221225477,exception={'code':'C0000005'},
                     fault_memory={'operation':1,'guest_offset':3},
                     sdk_guest_faults=[{'operation':'write','guest_address':3}])
        value['panic_capture']={'requested':True,'success':True,'errors':[],
            'caller':{'known':True,'saved_lr':0x824844F4},
            'reads':{'message':utfrow("The file '"+filename+"' contains unrecognizable data",0x8327C318),
                     'filename':utfrow(filename,0x41000000)}}
    elif kind=='native':
        value.update(unregistered_guest_target=0x82000000,exit_status=3221226505,
                     sdk_fatal_corroborated=True,fatal_stack=[{'index':0,'address':123}],
                     sdk_guest_faults=[],panic_capture={'requested':False,'success':False,'errors':[],'reads':{}})
    elif kind=='timeout':value.update(timed_out=True,exit_status=124)
    else:value.update(exception={'code':'C0000005'},exit_status=3221225477)
    return value


class DeploymentEvidenceTests(unittest.TestCase):
    def delta(self,base=None,modified=None):
        return compare_roots(inv({'default.xex':H} if base is None else base),inv({'default.xex':H,MEMBER:J} if modified is None else modified),MEMBER,J)

    def test_exact_delta_and_only_root_metadata_ignored(self):
        self.assertTrue(self.delta({'default.xex':H,'.staging.json':H},{'default.xex':H,'.staging.json':J,MEMBER:J})['valid'])
        self.assertFalse(self.delta(modified={'default.xex':H,MEMBER:J,'sub/.staging.json':H})['valid'])

    def test_changed_removed_extra_wrong_hash_rejected(self):
        for files in [{'default.xex':J,MEMBER:J},{MEMBER:J},{'default.xex':H,MEMBER:J,'extra':H},{'default.xex':H,MEMBER:H}]:
            self.assertFalse(self.delta(modified=files)['valid'])

    def test_existing_member_rejected(self):
        self.assertFalse(self.delta({'default.xex':H,MEMBER:J})['valid'])

    def test_path_guards(self):
        for member in ['/a','../a','a/../b','a//b','a\\b','C:a','a/./b','a/','a\x00b','a?b','.staging.json']:
            with self.subTest(member=member),self.assertRaises(ValueError):compare_roots(inv({}),inv({}),member,J)

    def test_reserved_windows_names_rejected(self):
        for member in ['CON','aux.txt','a/COM1.xxx','a/NUL','a/LPT9.bin']:
            with self.subTest(member=member),self.assertRaises(ValueError):compare_roots(inv({}),inv({}),member,J)

    def test_hash_type_case_and_length(self):
        for bad in [None,1,'A'*64,'a'*63,'g'*64]:
            with self.assertRaises(ValueError):compare_roots(inv({}),inv({}),MEMBER,bad)
        with self.assertRaises(ValueError):self.delta(modified={'default.xex':None,MEMBER:J})

    def test_inventory_shape_and_case_collisions(self):
        for bad in [{},{'files':[]},{'files':{'x':H,'X':J}}]:
            with self.assertRaises(ValueError):compare_roots(bad,inv({}),MEMBER,J)

    def test_caller_attestation_required(self):
        self.assertFalse(summarize_trials(report(),report('native'),report(),MEMBER)['limited_deployment_association'])
        self.assertTrue(summarize_trials(report(),report('native'),report(),MEMBER,identity_verified=True)['limited_deployment_association'])

    def test_failed_input_guards_no_association(self):
        for key in ['inputs_unchanged','game_input_unchanged']:
            for bad in [False,1,None,'true']:
                v=report();v[key]=bad
                self.assertFalse(summarize_trials(v,report('native'),report(),MEMBER,identity_verified=True)['limited_deployment_association'])

    def test_arbitrary_av_timeout_and_empty_groups_unresolved(self):
        for modified in [report('av'),report('timeout'),[]]:
            self.assertFalse(summarize_trials(report(),modified,report(),MEMBER,identity_verified=True)['limited_deployment_association'])
        self.assertFalse(summarize_trials([],report('native'),report(),MEMBER,identity_verified=True)['limited_deployment_association'])

    def test_filename_exact_known_prefix_only(self):
        for text in ['sample.xxx','../../'+MEMBER,'x/'+MEMBER,MEMBER.upper(),MEMBER+'x']:
            v=report();v['panic_capture']['reads']['filename']['text']=text
            self.assertFalse(summarize_trials(v,report('native'),report(),MEMBER,identity_verified=True)['limited_deployment_association'])

    def test_bad_capture_never_target(self):
        for mutation in ['decode_error','caller','errors','success','truncated']:
            v=report();p=v['panic_capture']
            if mutation=='decode_error':p['reads']['filename']['decode_error']='bad'
            elif mutation=='caller':p['caller']['saved_lr']=0
            elif mutation=='errors':p['errors']=['bad']
            elif mutation=='success':p['success']=False
            else:p['reads']['filename']['truncated']=True
            self.assertFalse(summarize_trials(v,report('native'),report(),MEMBER,identity_verified=True)['limited_deployment_association'])

    def test_mixed_trials_and_types_fail_closed(self):
        self.assertFalse(summarize_trials(report(),[report('native'),report('av')],report(),MEMBER,identity_verified=True)['limited_deployment_association'])
        for bad in [None,[1],'bad']:
            with self.assertRaises(ValueError):summarize_trials(bad,[],[],MEMBER)
        with self.assertRaises(ValueError):summarize_trials([],[],[],MEMBER,identity_verified=1)

    def test_heap_termination_without_capture_remains_unresolved(self):
        value=report('av')
        value.update(exit_status=0xC0000374,exception=None,run_record={'exit_status':0xC0000374})
        result=summarize_trials(report(),[report('other'),value],report(),MEMBER,identity_verified=True)
        self.assertFalse(result['limited_deployment_association'])
        row=result['trials']['modified'][1]
        self.assertEqual(row['observation'],'other_failure_or_observation_unresolved')
        self.assertFalse(row['different_positive_failure'])

    def test_heap_exit_does_not_validate_stale_panic_capture(self):
        value=report()
        value.update(exit_status=0xC0000374,run_record={'exit_status':0xC0000374})
        result=summarize_trials(value,report('other'),report(),MEMBER,identity_verified=True)
        self.assertFalse(result['trials']['baseline'][0]['specified_member_panic'])
        self.assertFalse(result['limited_deployment_association'])


class CrossFieldConsistencyTests(unittest.TestCase):
    def classification(self, value):
        return summarize_trials(value,[],[],MEMBER)['trials']['baseline'][0]

    def test_native_stale_target_arbitrary_av_rejected(self):
        value=report('native');value.update(exit_status=3221225477,exception={'code':'C0000005'},fault_memory={'operation':0,'guest_offset':0x43004e})
        self.assertFalse(self.classification(value)['different_positive_failure'])

    def test_native_timeout_exit0_and_wrong_exit_rejected(self):
        for changes in [{'timed_out':True},{'exit_status':0},{'exit_status':124},{'exit_status':True},{'exit_status':'3221226505'},{'timed_out':0},{'bounded_observation':True},{'diagnostic_success':1}]:
            value=report('native');value.update(changes)
            with self.subTest(changes=changes):self.assertFalse(self.classification(value)['different_positive_failure'])

    def test_native_requires_corroboration_no_guest_faults_or_panic(self):
        for changes in [{'sdk_fatal_corroborated':1},{'sdk_fatal_corroborated':False},{'fatal_stack':[]},{'sdk_guest_faults':[{'operation':'write','guest_address':3}]},{'panic_capture':report()['panic_capture']},{'panic_capture':[]},{'panic_capture':{'requested':1,'success':False,'errors':[],'reads':{}}}]:
            value=report('native');value.update(changes)
            with self.subTest(changes=changes):self.assertFalse(self.classification(value)['different_positive_failure'])

    def test_target_panic_requires_matching_exit_fault_and_guest3_write(self):
        changes=[{'exit_status':0},{'exit_status':3221226505},{'timed_out':True},{'exception':{'code':'C000001D'}},{'fault_memory':{'operation':0,'guest_offset':3}},{'fault_memory':{'operation':1,'guest_offset':4}},{'sdk_guest_faults':[]},{'sdk_guest_faults':[{'operation':'read','guest_address':3}]}]
        for change in changes:
            value=report();value.update(change)
            with self.subTest(change=change):self.assertFalse(self.classification(value)['specified_member_panic'])

    def test_panic_typed_flags_and_conflicting_native_rejected(self):
        for key,bad in [('requested',False),('requested',1),('success',1)]:
            value=report();value['panic_capture'][key]=bad
            self.assertFalse(self.classification(value)['specified_member_panic'])
        value=report();value['unregistered_guest_target']=0x82000000
        self.assertFalse(self.classification(value)['specified_member_panic'])

    def test_panic_message_filename_mismatch_and_wrong_buffer_rejected(self):
        for which in ['message','filename']:
            value=report();value['panic_capture']['reads'][which]['text']='other'
            self.assertFalse(self.classification(value)['specified_member_panic'])
        value=report();value['panic_capture']['reads']['message']['guest']=0x8327C31A
        self.assertFalse(self.classification(value)['specified_member_panic'])

    def test_utf16_text_hex_length_and_boolean_consistency(self):
        for changes in [{'hex':'0000'},{'captured':True},{'terminated':1},{'truncated':0},{'text':'A\0B'},{'word_known':1},{'guest':True}]:
            value=report();value['panic_capture']['reads']['filename'].update(changes)
            with self.subTest(changes=changes):self.assertFalse(self.classification(value)['specified_member_panic'])

    def test_run_record_exit_contradiction_is_unknown(self):
        for kind in ['target','native']:
            value=report(kind);value['run_record']={'exit_status':0}
            row=self.classification(value)
            self.assertFalse(row['specified_member_panic']);self.assertFalse(row['different_positive_failure'])

    def test_actual_report_shape_remains_classifiable(self):
        self.assertTrue(self.classification(report())['specified_member_panic'])
        self.assertTrue(self.classification(report('native'))['different_positive_failure'])
        self.assertTrue(self.classification(report('other'))['different_positive_failure'])
