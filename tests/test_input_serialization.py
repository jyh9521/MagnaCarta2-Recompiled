"""Input serialization contracts and real-header native fixture, not gameplay QA."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from tools.research import probe_title_entry as p

ROOT = Path(__file__).resolve().parents[1]


class InputSerializationTests(unittest.TestCase):
    def setUp(self):
        self.header = (ROOT/'src/host/input_serialization.h').read_text(encoding='utf-8')

    def test_all_refresh_entry_imports(self):
        for name in ('GetCapabilities', 'GetState', 'SetState', 'GetKeystroke'):
            self.assertIn('"__imp__XamInput'+name+'"', self.header)
        self.assertIn('kCount=4', self.header)

    def test_complete_preflight_before_mutation(self):
        install = self.header.split('inline bool InstallInputSerialization')[1]
        self.assertLess(install.index('if (!verified)'), install.index('GetProcAddress'))
        self.assertLess(install.index('if (!Plan('), install.index('if (!Exchange('))
        for guard in ('counts[n]!=1', 'IMAGE_FILE_MACHINE_AMD64', 'matching_dlls!=1'):
            self.assertIn(guard, self.header)

    def test_one_delegate_and_error_preservation(self):
        wrapper = self.header.split('template<size_t Api>')[1].split('inline const')[0]
        self.assertEqual(wrapper.count('original[Api](ctx,base)'), 1)
        self.assertIn('input_call_gate::Invoke(Api', wrapper)
        self.assertIn('errno=after_errno;SetLastError(after_error)', wrapper)
        for forbidden in ('ctx.r3=', 'WriteProcessMemory', 'GetDeviceState', 'printf'):
            self.assertNotIn(forbidden, wrapper)

    def test_default_off_and_process_rollback(self):
        host = (ROOT/'src/host/title_probe.cpp').read_text(encoding='utf-8')
        self.assertIn('MC2_SERIALIZE_INPUT', host)
        self.assertLess(host.index('InstallInputSerialization('), host.index('status=thread->Resume()'))
        self.assertNotIn('RestoreInputSerializationBeforeGuest(', host)
        self.assertIn('std::recursive_mutex mutex', (ROOT/'src/host/input_call_gate.h').read_text())

    def test_cli_opt_in_and_default(self):
        args = []
        for name in ('build-dir','generated','sdk','compiler','vcvars','xex','output'):
            args += ['--'+name, 'fixture']
        report = dict(diagnostic_success=True, bounded_observation=False)
        for enabled in (False, True):
            with self.subTest(enabled=enabled), patch.object(p,'os',SimpleNamespace(name='nt')), patch.object(p,'execute',return_value=report) as run:
                self.assertEqual(p.main(args+(['--serialize-input'] if enabled else [])), 0)
                self.assertEqual(run.call_args.args[0].serialize_input, enabled)

    @unittest.skipUnless(os.name == 'nt', 'Windows PE/IAT fixture')
    def test_actual_header_delegation_concurrency_plan_and_restore(self):
        from tools.research.compile_module import vc_environment
        compiler = ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe'
        sdk = ROOT/'local/upstream/rexglue/sdk/win-amd64'
        if not compiler.exists() or not sdk.exists():
            self.skipTest('local pinned SDK/compiler absent')
        evidence = ROOT/'local/analysis/phase36'
        evidence.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix='gate-fixture-',dir=evidence))
        env = vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'))
        cmd = [str(compiler),'/nologo','/std:c++latest','/EHa','/MD','/O2','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN',
               '/I'+str(sdk/'include'),'/I'+str(ROOT/'src/host'),str(ROOT/'tests/input_serialization_fixture.cpp'),
               '/Fe'+str(out/'fixture.exe'),'/Fo'+str(out/'fixture.obj')]
        result = subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=120)
        (out/'compile.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result = subprocess.run([str(out/'fixture.exe')],capture_output=True,text=True,timeout=60)
        (out/'run.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('INPUT_GATE_FIXTURE delegates=8008 peak=1 guards=9 exception_unlock=1 actual_restore=1',result.stdout)
        self.assertIn('INPUT_ABI pointer_bits=64 register_bits=64 context_alignment=64 state_bytes=16 caps_bytes=20 keystroke_bytes=8 endian=BE offsets=verified',result.stdout)
