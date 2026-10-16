import unittest
from tools.research.panic_capture_report import parse_panic_capture


def fixture(message='hello'):
    raw=(message+'\0').encode('utf-16be').hex().upper()
    return 'PANIC_GATE requested=1 matched=1 lr=82390A6C\n'+f'PANIC_READ tag=message guest=8327C318 status=ok captured={len(raw)//2} terminated=1 truncated=0 word_known=0 word=00000000 hex={raw}\n'+'PANIC_CALLER known=1 saved_lr=824844F4 r25=82000000 r26=40001000 r30=40002000\nPANIC_CAPTURE_END context_unchanged=1 resumes_guest=0\n'


class PanicCaptureTests(unittest.TestCase):
    def test_default_off(self):
        self.assertFalse(parse_panic_capture('')['requested'])

    def test_valid(self):
        value=parse_panic_capture(fixture())
        self.assertTrue(value['success']);self.assertEqual(value['reads']['message']['text'],'hello')

    def test_unicode_controls_preserved(self):
        value=parse_panic_capture(fixture('中文\n%s'))
        self.assertEqual(value['reads']['message']['text'],'中文\n%s')

    def test_no_end(self):
        self.assertFalse(parse_panic_capture(fixture().split('PANIC_CAPTURE_END')[0])['success'])

    def test_changed_context_or_resume(self):
        for value in ['context_unchanged=0 resumes_guest=0','context_unchanged=1 resumes_guest=1']:
            self.assertFalse(parse_panic_capture(fixture().replace('context_unchanged=1 resumes_guest=0',value))['success'])

    def test_duplicate_gate_or_read(self):
        for line in fixture().splitlines()[:2]:
            self.assertFalse(parse_panic_capture(fixture()+line+'\n')['success'])

    def test_wrong_gate_or_caller(self):
        for old,new in [('matched=1','matched=0'),('lr=82390A6C','lr=82390A70'),('saved_lr=824844F4','saved_lr=00000000')]:
            self.assertFalse(parse_panic_capture(fixture().replace(old,new))['success'])

    def test_truncated(self):
        self.assertFalse(parse_panic_capture(fixture().replace('truncated=0','truncated=1'))['success'])

    def test_length_and_encoding(self):
        for old,new in [('captured=12','captured=99999'),('00680065006C006C006F0000','D8000065006C006C006F0000')]:
            self.assertFalse(parse_panic_capture(fixture().replace(old,new))['success'])

    def test_failed_read_no_prefix(self):
        self.assertFalse(parse_panic_capture(fixture().replace('status=ok','status=unreadable'))['success'])

    def test_malformed_extra_gate(self):
        self.assertFalse(parse_panic_capture(fixture()+'PANIC_GATE malformed\n')['success'])

    def test_word_metadata_must_match_hex(self):
        row='PANIC_READ tag=header_word guest=40001000 status=ok captured=4 terminated=0 truncated=0 word_known=1 word=12345678 hex=00000000\n'
        self.assertFalse(parse_panic_capture(fixture()+row)['success'])

    def test_original_fault_continues(self):
        from pathlib import Path
        text=Path('src/host/title_probe.cpp').read_text(encoding='utf-8-sig')
        self.assertIn('ObserveOriginalPanic(*record,*c);',text)
        self.assertIn('return EXCEPTION_CONTINUE_SEARCH; // Record only:',text)
        self.assertIn('const PPCContext& c',text)

    def test_interior_nul_never_counts_as_decoded_success(self):
        value=parse_panic_capture(fixture('A\0B'))
        self.assertFalse(value['success'])
        self.assertNotIn('text',value['reads']['message'])
        self.assertIn('decode_error',value['reads']['message'])
