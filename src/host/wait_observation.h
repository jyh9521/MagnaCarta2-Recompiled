#pragma once
// Public-API-only metadata observation for the pinned ReXGlue 0.10.0 runtime.
// Never wait/poll/signal an object to infer its state. See RESEARCH_WAIT_OBJECT.md.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <string_view>

#include <rex/system/kernel_state.h>
#include <rex/system/xevent.h>
#include <rex/system/xsemaphore.h>
#include <rex/system/xthread.h>
#include <rex/thread/mutex.h>

namespace mc2::host {

inline constexpr char kWaitObservationRuntimeSha256[] =
    "e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a";

inline const char* WaitObjectTypeName(rex::system::XObject::Type type) {
  using Type = rex::system::XObject::Type;
  switch (type) {
    case Type::Undefined: return "undefined";
    case Type::Enumerator: return "enumerator";
    case Type::Event: return "event";
    case Type::File: return "file";
    case Type::IOCompletion: return "io-completion";
    case Type::Module: return "module";
    case Type::Mutant: return "mutant";
    case Type::NotifyListener: return "notify-listener";
    case Type::Semaphore: return "semaphore";
    case Type::Session: return "session";
    case Type::Socket: return "socket";
    case Type::SymbolicLink: return "symbolic-link";
    case Type::Thread: return "thread";
    case Type::Timer: return "timer";
  }
  return "unknown";
}

struct WaitObjectObservation {
  const char* status = "not-observed";
  rex::system::XObject::Type type = rex::system::XObject::Type::Undefined;
  uint32_t guest_object = 0;
  uint32_t primary_handle = 0;
  uint32_t aliases = 0;
  bool host_object = false;
  bool name_truncated = false;
  std::array<char, 257> name_hex{};  // At most 128 original name bytes, no log injection.
  bool event_type_known = false;
  uint32_t event_type = 0;
  bool semaphore_maximum_known = false;
  int32_t semaphore_maximum = 0;
  bool thread_metadata_known = false;
  uint32_t thread_id = 0;
  bool thread_running = false;
};

// Call only after the sampled guest thread has been resumed. This operation
// can fail closed with "busy" instead of blocking on the global critical region.
// The caller must verify the actual loaded SDK DLL against the constexpr SHA.
inline void ObserveWaitObject(rex::system::KernelState* kernel, uint32_t sample,
                              uint32_t handle, bool sdk_identity_verified) {
  WaitObjectObservation snapshot;
  if (!sdk_identity_verified) {
    snapshot.status = "unsupported-sdk";
  } else if (!kernel) {
    snapshot.status = "no-kernel";
  } else if (handle < rex::system::XObject::kHandleBase ||
             (handle & 3u) != 0) {
    snapshot.status = "unsupported-handle";
  } else {
    // Never perform printf, file I/O, waits, or state-changing calls under this lock.
    rex::thread::global_critical_region region;
    auto lock = region.TryAcquire();
    if (!lock.owns_lock()) {
      snapshot.status = "busy";
    } else {
      auto* table = kernel->object_table();
      auto object = table->LookupObject<rex::system::XObject>(handle);
      if (!object) {
        snapshot.status = "not-found";
      } else {
        snapshot.status = "observed";
        snapshot.type = object->type();
        snapshot.guest_object = object->guest_object();
        snapshot.host_object = object->is_host_object();
        const auto& handles = object->handles();
        snapshot.aliases = static_cast<uint32_t>(handles.size());
        snapshot.primary_handle = handles.empty() ? 0 : handles.front();
        const std::string_view name = object->name();
        const size_t count = std::min<size_t>(name.size(), 128);
        snapshot.name_truncated = name.size() > count;
        constexpr char hex[] = "0123456789ABCDEF";
        for (size_t i = 0; i < count; ++i) {
          const auto value = static_cast<unsigned char>(name[i]);
          snapshot.name_hex[2 * i] = hex[value >> 4];
          snapshot.name_hex[2 * i + 1] = hex[value & 15];
        }
        if (snapshot.type == rex::system::XObject::Type::Event) {
          auto event = table->LookupObject<rex::system::XEvent>(handle);
          if (event) {
            // Passing a state pointer would invoke Wait(...,0) in this SDK.
            // nullptr is mandatory: read reset kind only, never consume a signal.
            event->Query(&snapshot.event_type, nullptr);
            snapshot.event_type_known = true;
          }
        } else if (snapshot.type == rex::system::XObject::Type::Semaphore) {
          auto semaphore = table->LookupObject<rex::system::XSemaphore>(handle);
          if (semaphore) {
            snapshot.semaphore_maximum = semaphore->maximum_count();
            snapshot.semaphore_maximum_known = true;
          }
        } else if (snapshot.type == rex::system::XObject::Type::Thread) {
          auto thread = table->LookupObject<rex::system::XThread>(handle);
          if (thread) {
            snapshot.thread_id = thread->thread_id();
            snapshot.thread_running = thread->is_running();
            snapshot.thread_metadata_known = true;
          }
        }
      }
      // All retained object_ref instances release before the lock is destroyed.
    }
  }
  // Unknown fields stay explicitly unknown; zero is not an observed event state.
  std::printf(
      "TITLE_WAIT_OBJECT sample=%u handle=%08X status=%s type=%u type_name=%s "
      "guest=%08X host=%u primary=%08X aliases=%u name_hex=%s name_truncated=%u "
      "event_type_known=%u event_type=%u event_signal_known=0 "
      "semaphore_maximum_known=%u semaphore_maximum=%d semaphore_count_known=0 "
      "thread_metadata_known=%u thread_id=%u thread_running=%u "
      "refcount_known=0 producer_known=0 scope=public-readonly\n",
      sample, handle, snapshot.status, static_cast<uint32_t>(snapshot.type),
      WaitObjectTypeName(snapshot.type), snapshot.guest_object,
      unsigned(snapshot.host_object), snapshot.primary_handle, snapshot.aliases,
      snapshot.name_hex[0] ? snapshot.name_hex.data() : "-",
      unsigned(snapshot.name_truncated), unsigned(snapshot.event_type_known),
      snapshot.event_type, unsigned(snapshot.semaphore_maximum_known),
      snapshot.semaphore_maximum, unsigned(snapshot.thread_metadata_known),
      snapshot.thread_id, unsigned(snapshot.thread_running));
}

}  // namespace mc2::host
