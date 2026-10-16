"""Synthetic PPC address construction only; no game bytes or packages."""
import struct
import unittest
import contextlib
import io
from tools.research.audit_callback_sites import arguments, audit, direct_branch, scan

BASE=0x1000
TARGET=0x2000

def bl(address,target=TARGET):
    return 0x48000001|((target-address)&0x3FFFFFC)

def lis(reg,high):return 0x3C000000|(reg<<21)|(high&0xFFFF)
def addi(dest,source,low):return 0x38000000|(dest<<21)|(source<<16)|(low&0xFFFF)
def code(words):return struct.pack('>'+str(len(words))+'I',*words)
def sample():return [lis(11,0x1235),addi(5,0,4),addi(6,11,-0x8000),0x7FC4F378,bl(BASE+16)]


class CallbackSiteTests(unittest.TestCase):
    def test_input_modes_contract(self):
        args=arguments(['--xex','original.xex','--loader-source','pinned.cc','--output','result.json'])
        self.assertEqual(str(args.xex),'original.xex')
        self.assertIsNone(args.image)
        args=arguments(['--image','original.bin','--output','result.json'])
        self.assertIsNone(args.loader_source)

    def test_invalid_input_modes_rejected(self):
        for argv in (['--xex','x.xex'],['--image','x.bin','--loader-source','pinned.cc'],
                     ['--image','x.bin','--xex','x.xex','--loader-source','pinned.cc']):
            with self.subTest(argv=argv),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                arguments(argv+['--output','result.json'])

    def test_signed_pair_and_argument(self):
        result=scan(code(sample()),BASE,TARGET)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['target'],0x12348000)
        self.assertEqual(result[0]['status'],'static-candidate')
        self.assertEqual(result[0]['argument_register'],6)
        self.assertEqual(result[0]['range_size'],20)

    def test_negative_high_half_wrap(self):
        words=sample();words[0]=lis(11,0x82C2);words[2]=addi(6,11,-0x3E60)
        self.assertEqual(scan(code(words),BASE,TARGET)[0]['target'],0x82C1C1A0)

    def test_nonmatching_call_ignored(self):
        self.assertEqual(scan(code(sample()),BASE,0x3000),[])

    def test_unlinked_branch_ignored(self):
        words=sample();words[-1]&=~1
        self.assertEqual(scan(code(words),BASE,TARGET),[])

    def test_r6_clobber_fails_closed(self):
        words=sample();words[3]=addi(6,0,7)
        self.assertEqual(scan(code(words),BASE,TARGET)[0]['status'],'unresolved')

    def test_source_clobber_fails_closed(self):
        words=sample();words[1]=addi(11,0,7)
        self.assertEqual(scan(code(words),BASE,TARGET)[0]['reason'],'source-not-written-by-lis')

    def test_unknown_between_pair_rejected(self):
        words=sample();words[1]=0xFFFFFFFF
        self.assertEqual(scan(code(words),BASE,TARGET)[0]['reason'],'control-or-unknown-effects')

    def test_unknown_after_pair_rejected(self):
        words=sample();words[3]=0xFFFFFFFF
        self.assertEqual(scan(code(words),BASE,TARGET)[0]['status'],'unresolved')

    def test_call_after_pair_rejected(self):
        words=sample();words[3]=bl(BASE+12,0x3000)
        self.assertEqual(scan(code(words),BASE,TARGET)[0]['status'],'unresolved')

    def test_window_bound_rejected(self):
        self.assertEqual(scan(code(sample()),BASE,TARGET,window=2)[0]['status'],'unresolved')
        for window in (0,65):
            with self.assertRaisesRegex(ValueError,'window'):scan(b'',BASE,TARGET,window)

    def test_incoming_branch_bypassing_definition_rejected(self):
        words=[bl(BASE,BASE+12)]+sample()
        words[-1]=bl(BASE+20)
        result=scan(code(words),BASE,TARGET)[0]
        self.assertEqual(result['reason'],'branch-enters-definition-chain')

    def test_incoming_branch_to_lis_is_allowed(self):
        words=[bl(BASE,BASE+4)]+sample();words[-1]=bl(BASE+20)
        self.assertEqual(scan(code(words),BASE,TARGET)[0]['status'],'static-candidate')

    def test_conditional_branch_into_chain_rejected(self):
        words=[0x419A000C]+sample();words[-1]=bl(BASE+20)
        self.assertEqual(scan(code(words),BASE,TARGET)[0]['status'],'unresolved')

    def test_alignment_and_overflow_rejected(self):
        for data,base in [(b'x',BASE),(b'',BASE+1),(bytes(8),0xFFFFFFFC)]:
            with self.assertRaises(ValueError):scan(data,base,TARGET)

    def test_wrong_image_hash_rejected(self):
        with self.assertRaisesRegex(ValueError,'SHA-256'):audit(b'fixture')

    def test_relative_and_absolute_branch_decode(self):
        self.assertEqual(direct_branch(0x2000,bl(0x2000,0x1000)),(0x1000,True))
        self.assertEqual(direct_branch(BASE,0x48002003),(0x2000,True))
        self.assertIsNone(direct_branch(BASE,0x38600000))


if __name__=='__main__':unittest.main()
