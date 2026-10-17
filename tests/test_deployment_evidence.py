import copy
import unittest
from tools.research.deployment_evidence import compare_roots,summarize_trials

MEMBER='MC2Game/CookedXenon/sample.xxx'
H='a'*64
J='b'*64


def inv(files):return {'files':files}


def report(kind='target'):
    value={'inputs_unchanged':True,'game_input_unchanged':True,'image_loaded':True,
           'guest_entrypoint_launched':True,'diagnostic_success':True}
    if kind in ('target','other'):
        value['panic_capture']={'success':True,'errors':[],
            'caller':{'known':True,'saved_lr':0x824844F4},
            'reads':{'message':{'text':'captured message'},'filename':{
                'status':'ok','terminated':True,'truncated':False,
                'text':'..\\'+(MEMBER if kind=='target' else 'MC2Game/other.xxx').replace('/','\\')}}}
    elif kind=='native':value['unregistered_guest_target']=0x82000000
    elif kind=='timeout':value['timed_out']=True
    else:value['exception']={'code':'C0000005'}
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
