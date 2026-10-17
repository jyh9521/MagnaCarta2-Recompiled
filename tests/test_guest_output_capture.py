import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/guest_output_capture.h'


class GuestOutputCaptureTests(unittest.TestCase):
    def test_public_readback_called_once(self):
        text=HEADER.read_text(encoding='utf-8-sig')
        self.assertEqual(text.count('presenter->CaptureGuestOutput(image)'),1)
        self.assertIn('inline bool CaptureGuestOutput(rex::ui::Presenter* presenter,const char* path)',text)
    def test_no_paint_refresh_or_guest_mutation(self):
        text=HEADER.read_text(encoding='utf-8-sig')
        for forbidden in ['->Refresh','->Paint','RequestUIPaint','REX_STORE','WriteProcessMemory','VirtualProtect']:
            self.assertNotIn(forbidden,text)
    def test_original_sdk_contract(self):
        p=ROOT/'local/upstream/rexglue/sdk/win-amd64/include/rex/ui/presenter.h'
        if not p.is_file():self.skipTest('local pinned SDK absent')
        text=p.read_text(encoding='utf-8-sig')
        self.assertIn('R8 G8 B8 X8',text)
        self.assertIn('The last row is not required to be padded to the stride.',text)
        self.assertIn('virtual bool CaptureGuestOutput(RawImage& image_out) = 0;',text)
    def test_bounds_and_error_status_contract(self):
        text=HEADER.read_text(encoding='utf-8-sig')
        for status in ['dimensions-invalid','stride-invalid','data-short','span-overflow','span-limit','data-limit','file-open-failed','file-write-failed','file-close-failed','presenter-null','sdk-readback-failed','path-invalid']:
            self.assertIn('"'+status+'"',text)
    def test_close_checked_before_success(self):
        text=HEADER.read_text(encoding='utf-8-sig')
        self.assertLess(text.index('const int close_status=std::fclose(file);'),text.index('return "captured";'))
        self.assertIn('if(close_status!=0)return "file-close-failed";',text)

    @unittest.skipUnless(os.name=='nt','native Windows SDK fixture')
    def test_native_raw_image_fixture(self):
        compiler=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe'
        sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64'
        vcvars=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
        if not compiler.is_file() or not vcvars.is_file() or not (sdk/'include/rex/ui/presenter.h').is_file():self.skipTest('optional pinned compiler and SDK absent')
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertEqual(sha(compiler),'57e32b1ea2456f12f97bf802453171bbff12d56b2c486b4eca0c75343c0cda2c')
        folder=ROOT/'local/analysis/phase25';folder.mkdir(parents=True,exist_ok=True)
        out=Path(tempfile.mkdtemp(prefix='guest-output-fixture-',dir=folder))
        cpp=out/'fixture.cpp';exe=out/'fixture.exe'
        cpp.write_text(r'''
#include "guest_output_capture.h"
#include <fstream>
#include <iterator>
#include <string>
namespace capture=mc2::host::guest_output_capture;
int main(){
 rex::ui::RawImage image;image.width=2;image.height=2;image.stride=12;
 image.data={255,0,0,7,0,255,0,8,99,98,97,96,0,0,255,9,0,0,0,10};
 capture::Stats s;const auto original=image.data;
 if(std::string(capture::WriteRawImagePPM(image,"color.ppm",s))!="captured"||s.nonblack_pixels!=3||s.varied_pixels!=3||s.rgb_bytes!=12||s.data_bytes!=20||image.data!=original)return 1;
 image.stride=8;image.data.assign(16,0);for(size_t x=3;x<16;x+=4)image.data[x]=255;
 if(std::string(capture::WriteRawImagePPM(image,"black.ppm",s))!="captured"||s.nonblack_pixels||s.varied_pixels)return 2;
 for(size_t x=0;x<16;x+=4){image.data[x]=3;image.data[x+1]=4;image.data[x+2]=5;}
 if(std::string(capture::WriteRawImagePPM(image,"uniform.ppm",s))!="captured"||s.nonblack_pixels!=4||s.varied_pixels)return 3;
 const auto valid=image;
 auto invalid=[&](const char* expected){return std::string(capture::WriteRawImagePPM(image,"invalid.ppm",s))==expected && !std::ifstream("invalid.ppm").good();};
 image.width=0;if(!invalid("dimensions-invalid"))return 4;
 image=valid;image.height=0;if(!invalid("dimensions-invalid"))return 5;
 image=valid;image.width=8193;if(!invalid("dimensions-invalid"))return 6;
 image=valid;image.height=8193;if(!invalid("dimensions-invalid"))return 7;
 image=valid;image.stride=7;if(!invalid("stride-invalid"))return 8;
 image=valid;image.data.resize(15);if(!invalid("data-short"))return 9;
 image=valid;image.stride=SIZE_MAX;if(!invalid("span-overflow"))return 10;
 image=valid;image.stride=capture::kMaxBytes;if(!invalid("span-limit"))return 11;
 image=valid;image.data.resize(capture::kMaxBytes+1);if(!invalid("data-limit"))return 12;
 image=valid;
 if(std::string(capture::WriteRawImagePPM(image,"missing-dir/out.ppm",s))!="file-open-failed")return 13;
 if(std::string(capture::WriteRawImagePPM(image,nullptr,s))!="path-invalid")return 14;
 if(std::string(capture::WriteRawImagePPM(image,"bad path.ppm",s))!="path-invalid")return 15;
 if(mc2::host::CaptureGuestOutput(nullptr,"guest-output.ppm"))return 16;
 if(mc2::host::CaptureGuestOutput(nullptr,nullptr))return 17;
 if(std::ifstream("guest-output.ppm").good())return 18;
 FILE* readonly=std::fopen("color.ppm","rb");if(!readonly)return 19;
 const bool wrote=capture::WriteValidatedRows(readonly,image);const bool stream_error=std::ferror(readonly)!=0;
 const int closed=std::fclose(readonly);if(wrote||!stream_error||closed!=0)return 20;
 std::printf("RAW_IMAGE_FIXTURE cases=20 passed=1 scope=synthetic-rawimage-no-presenter-no-title\n");
 return 0;
}
''',encoding='utf-8')
        inputs={str(p):sha(p) for p in [HEADER,compiler,sdk/'include/rex/ui/presenter.h',cpp]}
        report={'scope':'Actual header with SDK RawImage on owned synthetic buffers; no Presenter instance, SDK capture or title execution.','success':False,'inputs':inputs}
        try:
            from tools.research.compile_module import vc_environment
            command=[str(compiler),'/nologo','/Brepro','/std:c++latest','/O2','/MD','/EHa','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/I'+str(HEADER.parent),'/I'+str(sdk/'include'),str(cpp),'/Fo'+str(out/'fixture.obj'),'/Fe'+str(exe),'/link','/Brepro']
            proc=subprocess.run(command,cwd=out,env=vc_environment(vcvars),capture_output=True,text=True,timeout=120)
            (out/'compile.txt').write_text(proc.stdout+proc.stderr,encoding='utf-8');report.update(compile_command=command,compile_exit=proc.returncode)
            self.assertEqual(proc.returncode,0,str(out))
            run=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            (out/'run.txt').write_text(run.stdout+run.stderr,encoding='utf-8');report.update(run_exit=run.returncode,stdout=run.stdout,stderr=run.stderr)
            self.assertEqual(run.returncode,0,str(out));self.assertFalse(run.stderr)
            self.assertIn('cases=20 passed=1',run.stdout)
            expected={'color.ppm':b'P6\n2 2\n255\n'+bytes([255,0,0,0,255,0,0,0,255,0,0,0]),'black.ppm':b'P6\n2 2\n255\n'+bytes(12),'uniform.ppm':b'P6\n2 2\n255\n'+bytes([3,4,5])*4}
            for name,data in expected.items():self.assertEqual((out/name).read_bytes(),data)
            self.assertIn('status=presenter-null path=guest-output.ppm',run.stdout)
            self.assertIn('status=path-invalid path=-',run.stdout)
            self.assertFalse((out/'invalid.ppm').exists());self.assertFalse((out/'guest-output.ppm').exists())
            report['ppm_files']={name:{'sha256':sha(out/name),'bytes':len(data)} for name,data in expected.items()}
            report['inputs_unchanged']=all(sha(Path(p))==v for p,v in inputs.items());self.assertTrue(report['inputs_unchanged'])
            report['success']=True
        finally:
            path=out/'verification.json';path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');json.loads(path.read_text())

if __name__=='__main__':unittest.main()
