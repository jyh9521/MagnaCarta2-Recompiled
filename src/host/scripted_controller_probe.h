#pragma once
// Explicit synthetic automatic-input experiment, never physical-controller QA.
// InputSystem and SlotAssignment remain the unmodified typed SDK implementations.
#include <Windows.h>
#include <rex/input/input_driver.h>
#include <rex/ui/virtual_key.h>
#include <array>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <mutex>
namespace mc2::host {
namespace scripted_controller {
using namespace rex::input;
using rex::X_RESULT;using rex::X_STATUS;
using Clock=uint64_t(*)();
inline uint64_t Now(){return GetTickCount64();}
inline constexpr DeviceId kDevice=DeviceId(0x5343524950540001ULL);
inline constexpr uint64_t kPulseStart=25000,kPulseWidth=500;
// Windows SDK 10.0.26100.0 um/Xinput.h defines GAMEPAD subtype as 0x01.
// Deliberately do not include Xinput.h: its macros collide with SDK enum names.
inline constexpr uint8_t kGamepadSubtype=1;
static_assert(X_INPUT_GAMEPAD_START==0x10);
struct Snapshot {
 bool made=false,setup=false,armed=false,neutral_only=false,down_emitted=false,up_emitted=false;
 uint64_t arm_tick=0,max_elapsed=0,setup_calls=0,polls=0,pressed_polls=0,released_polls=0,first_tick=0,last_tick=0,capabilities=0,keystroke_polls=0,key_down=0,key_up=0,empty=0,vibration=0,errors=0;
 uint32_t packet=1;uint16_t left=0,right=0;
};
struct Shared {std::mutex mutex;Snapshot data;};
inline Shared shared;
inline uint32_t Phase(Snapshot& s,uint64_t tick){if(!s.armed||s.neutral_only)return 0;const auto elapsed=tick>=s.arm_tick?tick-s.arm_tick:0;if(elapsed>s.max_elapsed)s.max_elapsed=elapsed;return s.max_elapsed<kPulseStart?0:s.max_elapsed<kPulseStart+kPulseWidth?1:2;}
// Methods serialize only this synthetic driver's state. No is_active()/focus
// gate: the opt-in pulse is deliberately observable with a hidden test window.
// Defensive driver contract (not a claim of one mandated SDK null error):
// wrong ID/not-Setup => DEVICE_NOT_CONNECTED; null/unsupported flags => BAD_ARGUMENTS.
// Failed calls never overwrite caller output. No physical vibration is emitted.
class Driver final:public InputDriver {
 Clock clock_;
 X_RESULT Check(DeviceId id,const void* out,Snapshot& s){if(id!=kDevice||!s.setup){++s.errors;return X_ERROR_DEVICE_NOT_CONNECTED;}if(!out){++s.errors;return X_ERROR_BAD_ARGUMENTS;}return X_ERROR_SUCCESS;}
 public:
 explicit Driver(Clock clock):InputDriver(nullptr,0),clock_(clock){}
 X_STATUS Setup() override {std::lock_guard lock(shared.mutex);auto& s=shared.data;s.setup=true;++s.setup_calls;return X_STATUS_SUCCESS;}
 void EnumerateDevices(std::vector<DeviceInfo>& out) override {std::lock_guard lock(shared.mutex);if(!shared.data.setup)return;DeviceInfo d;d.id=kDevice;d.ordinal=0;d.name="Scripted START probe (synthetic)";d.guid="scripted-start-v1";d.synthetic=true;out.push_back(std::move(d));}
 X_RESULT GetDeviceState(DeviceId id,X_INPUT_STATE* out) override {std::lock_guard lock(shared.mutex);auto& s=shared.data;const auto valid=Check(id,out,s);if(valid)return valid;const auto tick=clock_();const auto phase=Phase(s,tick);X_INPUT_STATE value{};value.packet_number=phase+1;value.gamepad.buttons=phase==1?X_INPUT_GAMEPAD_START:0;*out=value;if(!s.polls)s.first_tick=tick;s.last_tick=tick;++s.polls;if(phase==1)++s.pressed_polls;else if(phase==2)++s.released_polls;s.packet=phase+1;return X_ERROR_SUCCESS;}
 X_RESULT GetDeviceCapabilities(DeviceId id,uint32_t flags,X_INPUT_CAPABILITIES* out) override {std::lock_guard lock(shared.mutex);auto& s=shared.data;const auto valid=Check(id,out,s);if(valid)return valid;if(flags!=0&&flags!=X_INPUT_FLAG_GAMEPAD){++s.errors;return X_ERROR_BAD_ARGUMENTS;}X_INPUT_CAPABILITIES value{};value.type=XINPUT_DEVTYPE_GAMEPAD;value.sub_type=kGamepadSubtype;value.gamepad.buttons=X_INPUT_GAMEPAD_START;/* No physical/FFB capability claim. */*out=value;++s.capabilities;return X_ERROR_SUCCESS;}
 X_RESULT SetDeviceVibration(DeviceId id,X_INPUT_VIBRATION* value) override {std::lock_guard lock(shared.mutex);auto& s=shared.data;const auto valid=Check(id,value,s);if(valid)return valid;s.left=value->left_motor_speed;s.right=value->right_motor_speed;++s.vibration;return X_ERROR_SUCCESS;}
 X_RESULT GetDeviceKeystroke(DeviceId id,uint32_t flags,X_INPUT_KEYSTROKE* out) override {std::lock_guard lock(shared.mutex);auto& s=shared.data;const auto valid=Check(id,out,s);if(valid)return valid;if(flags!=0&&flags!=X_INPUT_FLAG_GAMEPAD){++s.errors;return X_ERROR_BAD_ARGUMENTS;}++s.keystroke_polls;const auto phase=Phase(s,clock_());uint16_t transition=0;if(phase==1&&!s.down_emitted){s.down_emitted=true;++s.key_down;transition=X_INPUT_KEYSTROKE_KEYDOWN;}else if(phase==2&&s.down_emitted&&!s.up_emitted){s.up_emitted=true;++s.key_up;transition=X_INPUT_KEYSTROKE_KEYUP;}if(!transition){++s.empty;return X_ERROR_EMPTY;}X_INPUT_KEYSTROKE value{};value.virtual_key=uint16_t(rex::ui::VirtualKey::kXInputPadStart);value.flags=transition;value.user_index=0;*out=value;return X_ERROR_SUCCESS;}
};
} // namespace scripted_controller
// Factory does not initialize or add the driver. Caller checks Setup then uses
// InputSystem::AddDriver; no default driver/assignment is replaced.
inline std::unique_ptr<rex::input::InputDriver> MakeScriptedController(scripted_controller::Clock clock=&scripted_controller::Now,bool neutral_only=false){using namespace scripted_controller;std::lock_guard lock(shared.mutex);if(shared.data.made||!clock)return {};shared.data.made=true;shared.data.neutral_only=neutral_only;return std::make_unique<Driver>(clock);}
inline bool ArmScriptedController(uint64_t tick=GetTickCount64()){using namespace scripted_controller;std::lock_guard lock(shared.mutex);auto& s=shared.data;if(!s.made||!s.setup||s.armed)return false;s.armed=true;s.arm_tick=tick;s.max_elapsed=0;s.packet=1;return true;}
inline scripted_controller::Snapshot SnapshotScriptedController(){std::lock_guard lock(scripted_controller::shared.mutex);return scripted_controller::shared.data;}
inline void DumpScriptedController(FILE* out=stdout){if(!out)return;const auto s=SnapshotScriptedController();std::fprintf(out,"SCRIPTED_CONTROLLER input_source=synthetic automatic_only=1 physical_verified=0 made=%u setup=%u armed=%u neutral_only=%u device=%llX pulse_start_ms=25000 pulse_width_ms=500 arm_tick=%llu polls=%llu pressed_polls=%llu released_polls=%llu packet=%u first_tick=%llu last_tick=%llu capabilities=%llu keystroke_polls=%llu key_down=%llu key_up=%llu empty=%llu vibration=%llu left=%u right=%u errors=%llu setup_calls=%llu\n",unsigned(s.made),unsigned(s.setup),unsigned(s.armed),unsigned(s.neutral_only),(unsigned long long)scripted_controller::kDevice,(unsigned long long)s.arm_tick,(unsigned long long)s.polls,(unsigned long long)s.pressed_polls,(unsigned long long)s.released_polls,s.packet,(unsigned long long)s.first_tick,(unsigned long long)s.last_tick,(unsigned long long)s.capabilities,(unsigned long long)s.keystroke_polls,(unsigned long long)s.key_down,(unsigned long long)s.key_up,(unsigned long long)s.empty,(unsigned long long)s.vibration,unsigned(s.left),unsigned(s.right),(unsigned long long)s.errors,(unsigned long long)s.setup_calls);}
} // namespace mc2::host
