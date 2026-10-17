"""Typed synthetic controller, not physical input or title acceptance."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/scripted_controller_probe.h'
class ScriptedControllerTests(unittest.TestCase):
 def test_typed_driver_and_no_system_replacement(self):
  s=HEADER.read_text();self.assertIn('public InputDriver',s);self.assertNotIn('public IInputSystem',s);self.assertNotIn('SetDeviceAssignment(',s);self.assertIn('d.synthetic=true',s);self.assertIn('d.ordinal=0',s)
 def test_neutral_present_control_mode(self):
  s=HEADER.read_text();self.assertIn('neutral_only=false',s);self.assertIn('!s.armed||s.neutral_only',s);self.assertIn('neutral_only=%u',s)
 def test_time_based_not_poll_extended(self):
  s=HEADER.read_text();self.assertIn('kPulseStart=25000,kPulseWidth=500',s);self.assertIn('tick>=s.arm_tick?tick-s.arm_tick:0',s);self.assertIn('s.max_elapsed=elapsed',s);self.assertNotIn('Sleep(',s)
 def test_off_by_default_and_no_focus_suppression(self):
  s=HEADER.read_text();self.assertIn('made=false,setup=false,armed=false',s);self.assertNotIn('if(is_active()',s);self.assertIn('physical_verified=0',s)
 def test_official_typed_returns_and_start_key(self):
  s=HEADER.read_text()
  for token in ['X_ERROR_EMPTY','X_ERROR_BAD_ARGUMENTS','X_ERROR_DEVICE_NOT_CONNECTED','X_STATUS_SUCCESS','X_INPUT_GAMEPAD_START','VirtualKey::kXInputPadStart','X_INPUT_KEYSTROKE_KEYDOWN','X_INPUT_KEYSTROKE_KEYUP']:self.assertIn(token,s)
 def test_shared_state_serialized_and_callback_without_poll_extension(self):
  s=HEADER.read_text();self.assertIn('std::mutex',s);self.assertIn('std::lock_guard',s);self.assertIn('phase==2&&s.down_emitted&&!s.up_emitted',s)
 def test_no_virtual_os_device_or_sdk_patching(self):
  s=HEADER.read_text()
  for bad in ['WriteProcessMemory','VirtualProtect','CreateFile(','DeviceIoControl','REX_HOOK_RAW','__imp__','XInputSetState']:self.assertNotIn(bad,s)
 @unittest.skipUnless(os.name=='nt','Windows SDK native input fixture')
 def test_native_driver_and_real_input_system(self):
  from tools.research.compile_module import vc_environment
  from tools.research.probe_route_a import CLANG_CL_SHA256
  cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64'
  if not cc.exists() or not sdk.exists():self.skipTest('optional pinned SDK/compiler absent')
  self.assertEqual(hashlib.sha256(cc.read_bytes()).hexdigest(),CLANG_CL_SHA256)
  self.assertEqual(hashlib.sha256((sdk/'bin/rexruntime.dll').read_bytes()).hexdigest(),'e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a')
  out=Path(tempfile.mkdtemp(prefix='controller-native-',dir=ROOT/'local/analysis/phase26'));source=out/'fixture.cpp';source.write_text(CPP)
  files=[HEADER,sdk/'include/rex/input/input_driver.h',sdk/'include/rex/input/input_system.h',sdk/'include/rex/input/device_assignment.h',sdk/'include/rex/input/input.h',sdk/'bin/rexruntime.dll'];hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
  cmd=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/fp:strict','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/I'+str(sdk/'include'),'/I'+str(HEADER.parent),str(source),'/Fe'+str(out/'fixture.exe'),'/Fo'+str(out/'fixture.obj'),'/link','/LIBPATH:'+str(sdk/'lib'),'rexruntime.lib','spdlog.lib','fmt.lib']
  env=vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'));key=next(k for k in env if k.lower()=='path');env[key]=str(sdk/'bin')+os.pathsep+env[key]
  v=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=120);r={'compile_command':cmd,'compile_exit':v.returncode,'inputs':hashes,'runs':[]};(out/'compile.txt').write_text(v.stdout+v.stderr);(out/'verification.json').write_text(json.dumps(r,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr)
  for scenario in ['direct','missed','system','neutral']:
   v=subprocess.run([str(out/'fixture.exe'),scenario],cwd=out,env=env,capture_output=True,text=True,timeout=30);(out/(scenario+'.txt')).write_text(v.stdout+v.stderr);r['runs'].append({'command':[str(out/'fixture.exe'),scenario],'exit_status':v.returncode,'literal_output':v.stdout});r['inputs_unchanged']=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items());(out/'verification.json').write_text(json.dumps(r,indent=2));self.assertEqual(v.returncode,0,v.stdout+v.stderr);self.assertTrue(r['inputs_unchanged']);self.assertIn('SCRIPTED_CONTROLLER_FIXTURE scenario='+scenario+' success=1 physical_verified=0',v.stdout)
CPP=r'''
#include "scripted_controller_probe.h"
#include <rex/input/input_system.h>
#include <Xinput.h>
#include <cassert>
#include <atomic>
#include <thread>
#include <vector>
#include <type_traits>
using namespace mc2::host;
using namespace mc2::host::scripted_controller;
using namespace rex::input;
static_assert(kGamepadSubtype==XINPUT_DEVSUBTYPE_GAMEPAD);
static_assert(uint16_t(rex::ui::VirtualKey::kXInputPadStart)==VK_PAD_START);
std::atomic<uint64_t> tick{0};uint64_t ClockNow(){return tick.load();}
void State(InputDriver& d,uint64_t now,uint32_t packet,uint16_t buttons){tick=now;X_INPUT_STATE s;std::memset(&s,0xA5,sizeof(s));assert(d.GetDeviceState(kDevice,&s)==X_ERROR_SUCCESS);assert(uint32_t(s.packet_number)==packet&&uint16_t(s.gamepad.buttons)==buttons);auto*b=(uint8_t*)&s;assert(b[0]==0&&b[1]==0&&b[2]==0&&b[3]==packet&&b[4]==0&&b[5]==buttons);for(size_t i=6;i<sizeof(s);++i)assert(b[i]==0);}
int main(int argc,char** argv){assert(argc==2);assert(std::setvbuf(stdout,nullptr,_IONBF,0)==0);const bool system=!std::strcmp(argv[1],"system"),neutral=!std::strcmp(argv[1],"neutral");assert(!MakeScriptedController(nullptr));auto d=MakeScriptedController(ClockNow,neutral);assert(d&&!MakeScriptedController(ClockNow));X_INPUT_STATE before{};assert(d->GetDeviceState(kDevice,&before)==X_ERROR_DEVICE_NOT_CONNECTED);assert(!ArmScriptedController(1000));assert(d->Setup()==X_STATUS_SUCCESS&&d->Setup()==X_STATUS_SUCCESS);tick=1000;assert(ArmScriptedController(ClockNow())&&!ArmScriptedController(ClockNow()));d->set_is_active_callback([]{return false;});
if(neutral){std::vector<DeviceInfo> devices;d->EnumerateDevices(devices);assert(devices.size()==1&&devices[0].id==kDevice&&devices[0].synthetic);X_INPUT_KEYSTROKE key{},before{};std::memset(&key,0xA5,sizeof(key));before=key;for(uint64_t now:std::array<uint64_t,10>{0,999,1000,25999,26000,26499,26500,30000,100000000,UINT64_MAX}){State(*d,now,1,0);assert(d->GetDeviceKeystroke(kDevice,0,&key)==X_ERROR_EMPTY&&!std::memcmp(&key,&before,sizeof(key)));}State(*d,0,1,0);auto input=CreateDefaultInputSystem(true);assert(input&&input->Setup()==X_STATUS_SUCCESS);input->AddDriver(std::move(d));input->SetActiveCallback([]{return false;});for(uint64_t now:std::array<uint64_t,4>{26000,26500,100000000,UINT64_MAX}){tick=now;X_INPUT_STATE state{};assert(input->GetState(0,&state)==X_ERROR_SUCCESS&&uint16_t(state.gamepad.buttons)==0);assert(input->GetKeystroke(0,0,&key)==X_ERROR_EMPTY);}X_INPUT_CAPABILITIES caps{};assert(input->GetCapabilities(0,0,&caps)==X_ERROR_SUCCESS&&caps.type==1&&caps.sub_type==1);const auto snap=SnapshotScriptedController();assert(snap.made&&snap.setup&&snap.armed&&snap.neutral_only&&snap.packet==1&&snap.key_down==0&&snap.key_up==0&&snap.pressed_polls==0&&snap.released_polls==0);input->Shutdown();}
else if(system){auto input=CreateDefaultInputSystem(true);assert(input);assert(input->Setup()==X_STATUS_SUCCESS);auto* identity=input.get();input->AddDriver(std::move(d));assert(input.get()==identity);input->SetActiveCallback([]{return false;});tick=26000;X_INPUT_STATE s{};assert(input->GetState(0,&s)==X_ERROR_SUCCESS&&(uint16_t(s.gamepad.buttons)&X_INPUT_GAMEPAD_START));assert(input->GetState(3,&s)==X_ERROR_DEVICE_NOT_CONNECTED);X_INPUT_CAPABILITIES caps{};assert(input->GetCapabilities(0,0,&caps)==X_ERROR_SUCCESS&&caps.type==1&&caps.sub_type==1);input->Shutdown();}
else if(!std::strcmp(argv[1],"missed")){State(*d,30000,3,0);X_INPUT_KEYSTROKE key{};for(unsigned i=0;i<3;++i)assert(d->GetDeviceKeystroke(kDevice,0,&key)==X_ERROR_EMPTY);State(*d,26000,3,0);assert(d->GetDeviceKeystroke(kDevice,0,&key)==X_ERROR_EMPTY);auto snap=SnapshotScriptedController();assert(snap.key_down==0&&snap.key_up==0&&snap.pressed_polls==0);}
else{std::vector<DeviceInfo> devices;DeviceInfo prior;prior.id=DeviceId(999);devices.push_back(prior);d->EnumerateDevices(devices);assert(devices.size()==2&&devices[0].id==DeviceId(999)&&devices[1].id==kDevice&&devices[1].synthetic&&devices[1].ordinal==0);X_INPUT_STATE s{},copy{};std::memset(&s,0xA5,sizeof(s));copy=s;assert(d->GetDeviceState(DeviceId::kInvalid,&s)==X_ERROR_DEVICE_NOT_CONNECTED&&!std::memcmp(&s,&copy,sizeof(s)));assert(d->GetDeviceState(kDevice,nullptr)==X_ERROR_BAD_ARGUMENTS);X_INPUT_CAPABILITIES caps{},caps_before{};std::memset(&caps,0xA5,sizeof(caps));caps_before=caps;assert(d->GetDeviceCapabilities(kDevice,99,&caps)==X_ERROR_BAD_ARGUMENTS&&!std::memcmp(&caps,&caps_before,sizeof(caps)));assert(d->GetDeviceCapabilities(kDevice,0,&caps)==X_ERROR_SUCCESS&&caps.type==1&&caps.sub_type==XINPUT_DEVSUBTYPE_GAMEPAD&&uint16_t(caps.flags)==0&&uint16_t(caps.gamepad.buttons)==X_INPUT_GAMEPAD_START);assert(d->GetDeviceCapabilities(kDevice,0,nullptr)==X_ERROR_BAD_ARGUMENTS);const auto badcaps=caps;assert(d->GetDeviceCapabilities(DeviceId::kInvalid,0,&caps)==X_ERROR_DEVICE_NOT_CONNECTED&&!std::memcmp(&caps,&badcaps,sizeof(caps)));
X_INPUT_KEYSTROKE key{},sentinel{};std::memset(&key,0xA5,sizeof(key));sentinel=key;tick=1000;assert(d->GetDeviceKeystroke(kDevice,0,&key)==X_ERROR_EMPTY&&!std::memcmp(&key,&sentinel,sizeof(key)));State(*d,999,1,0);State(*d,25999,1,0);State(*d,26000,2,0x10);assert(d->GetDeviceKeystroke(kDevice,0,&key)==X_ERROR_SUCCESS&&uint16_t(key.virtual_key)==VK_PAD_START&&uint16_t(key.flags)==X_INPUT_KEYSTROKE_KEYDOWN&&key.user_index==0);assert(((uint8_t*)&key)[0]==0x58&&((uint8_t*)&key)[1]==0x14);assert(d->GetDeviceKeystroke(kDevice,0,&key)==X_ERROR_EMPTY);State(*d,26499,2,0x10);State(*d,26500,3,0);assert(d->GetDeviceKeystroke(kDevice,0,&key)==X_ERROR_SUCCESS&&uint16_t(key.flags)==X_INPUT_KEYSTROKE_KEYUP);assert(d->GetDeviceKeystroke(kDevice,0,&key)==X_ERROR_EMPTY);State(*d,26000,3,0);assert(d->GetDeviceKeystroke(kDevice,0,&key)==X_ERROR_EMPTY);assert(d->GetDeviceKeystroke(kDevice,99,&key)==X_ERROR_BAD_ARGUMENTS);assert(d->GetDeviceKeystroke(kDevice,0,nullptr)==X_ERROR_BAD_ARGUMENTS);const auto badkey=key;assert(d->GetDeviceKeystroke(DeviceId::kInvalid,0,&key)==X_ERROR_DEVICE_NOT_CONNECTED&&!std::memcmp(&key,&badkey,sizeof(key)));
X_INPUT_VIBRATION vibration{};vibration.left_motor_speed=0x1234;vibration.right_motor_speed=0xFEDC;const auto vibration_before=vibration;assert(d->SetDeviceVibration(kDevice,&vibration)==X_ERROR_SUCCESS&&!std::memcmp(&vibration,&vibration_before,sizeof(vibration)));assert(d->SetDeviceVibration(kDevice,nullptr)==X_ERROR_BAD_ARGUMENTS);assert(d->SetDeviceVibration(DeviceId::kInvalid,&vibration)==X_ERROR_DEVICE_NOT_CONNECTED&&!std::memcmp(&vibration,&vibration_before,sizeof(vibration)));tick=30000;const auto start=SnapshotScriptedController().polls;std::vector<std::thread> threads;for(unsigned i=0;i<4;++i)threads.emplace_back([&]{for(unsigned j=0;j<1000;++j){X_INPUT_STATE state{};assert(d->GetDeviceState(kDevice,&state)==X_ERROR_SUCCESS&&uint32_t(state.packet_number)==3&&uint16_t(state.gamepad.buttons)==0);}});for(auto&t:threads)t.join();const auto snap=SnapshotScriptedController();assert(snap.polls==start+4000&&snap.key_down==1&&snap.key_up==1&&snap.left==0x1234&&snap.right==0xFEDC&&snap.pressed_polls==2&&snap.packet==3);}
DumpScriptedController();DumpScriptedController(nullptr);std::printf("SCRIPTED_CONTROLLER_FIXTURE scenario=%s success=1 physical_verified=0\n",argv[1]);}
'''
