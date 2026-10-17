import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools.research.guest_output_capture_report import parse_guest_output_capture
class GuestOutputReportTests(unittest.TestCase):
    def text(self):return 'TITLE_WAIT_SDK parent_attested=1\nTITLE_GUEST_OUTPUT_CAPTURE enabled=1 sdk_guard=1 configured=1\nGUEST_OUTPUT_CAPTURE requested=1 status=captured path=guest-output.ppm width=2 height=1 stride=8 data_bytes=8 rgb_bytes=6 nonblack_pixels=1 varied_pixels=1 sdk_readback=1\nGUEST_OUTPUT_CAPTURE_TIMING elapsed_ms=2 scheduling_perturbed=1 visible_present_proof=0\n'
    def load(self,text=None,data=b'P6\n2 1\n255\n\0\0\0\xff\0\0',missing=False):
        with tempfile.TemporaryDirectory()as d:
            if not missing:Path(d,'guest-output.ppm').write_bytes(data)
            return parse_guest_output_capture(text or self.text(),d,True)
    def test_valid(self):self.assertTrue(self.load()['capture_verified'])
    def test_disabled(self):self.assertEqual(parse_guest_output_capture('',Path('.'))['status'],'disabled')
    def test_not_visible(self):self.assertFalse(self.load()['visible_present_proof'])
    def test_stats(self):self.assertEqual(self.load()['nonblack_pixels'],1)
    def test_missing(self):self.assertFalse(self.load(missing=True)['attempt_verified'])
    def test_wrong_pixels(self):self.assertFalse(self.load(data=b'P6\n2 1\n255\n\0\0\0\0\0\0')['capture_verified'])
    def test_truncated(self):self.assertFalse(self.load(data=b'P6\n2 1\n255\n\0\0')['capture_verified'])
    def test_wrong_stride(self):self.assertFalse(self.load(self.text().replace('stride=8','stride=7'))['capture_verified'])
    def test_oversize(self):self.assertFalse(self.load(self.text().replace('width=2','width=8193'))['capture_verified'])
    def test_bad_sdk(self):self.assertFalse(self.load(self.text().replace('parent_attested=1','parent_attested=0'))['attempt_verified'])
    def test_bad_config(self):self.assertFalse(self.load(self.text().replace('sdk_guard=1','sdk_guard=0'))['attempt_verified'])
    def test_false_failure_retained(self):
        s=self.text().replace('status=captured','status=sdk-readback-failed').replace('sdk_readback=1','sdk_readback=0')
        import re
        for k in ['width','height','stride','data_bytes','rgb_bytes','nonblack_pixels','varied_pixels']:s=re.sub(k+r'=\d+',k+'=0',s)
        j=self.load(s);self.assertTrue(j['attempt_verified']);self.assertFalse(j['capture_verified'])
    def test_bare_frame(self):self.assertFalse(self.load(self.text()+'GUEST_OUTPUT_CAPTURE')['attempt_verified'])
    def test_duplicate(self):self.assertFalse(self.load(self.text()+self.text())['attempt_verified'])
    def test_path(self):self.assertFalse(self.load(self.text().replace('path=guest-output.ppm','path=../guest-output.ppm'))['attempt_verified'])
    def test_read_error(self):
        with patch.object(Path,'read_bytes',side_effect=OSError('retained')):self.assertFalse(self.load()['capture_verified'])

    def test_failure_cannot_carry_pixels(self):self.assertFalse(self.load(self.text().replace('status=captured','status=sdk-readback-failed').replace('sdk_readback=1','sdk_readback=0'))['attempt_verified'])

    def test_file_failure_requires_readback(self):self.assertFalse(self.load(self.text().replace('status=captured','status=file-open-failed').replace('sdk_readback=1','sdk_readback=0'))['attempt_verified'])
    def test_file_failure_retained(self):
        j=self.load(self.text().replace('status=captured','status=file-open-failed'));self.assertTrue(j['attempt_verified']);self.assertFalse(j['capture_verified'])
    def test_validation_failure_cannot_carry_rgb(self):self.assertFalse(self.load(self.text().replace('status=captured','status=dimensions-invalid'))['attempt_verified'])
    def test_validation_failure_retained(self):
        s=self.text().replace('status=captured','status=dimensions-invalid').replace('width=2','width=0').replace('rgb_bytes=6','rgb_bytes=0').replace('nonblack_pixels=1','nonblack_pixels=0').replace('varied_pixels=1','varied_pixels=0')
        self.assertTrue(self.load(s)['attempt_verified'])
