#pragma once
// Shared gate for all complete SDK input API calls; not a driver-local lock.
#include <array>
#include <atomic>
#include <cstdint>
#include <mutex>
namespace mc2::host::input_call_gate {
inline std::recursive_mutex mutex;
inline std::array<std::atomic<uint64_t>,4> calls{},completed{};
inline std::atomic<uint64_t> active{0},peak{0};
template<class Delegate> void Invoke(size_t api, Delegate&& delegate) {
  std::lock_guard lock(mutex);
  calls[api].fetch_add(1,std::memory_order_relaxed);
  const auto count=active.fetch_add(1,std::memory_order_relaxed)+1;
  auto old=peak.load(std::memory_order_relaxed);
  while(old<count && !peak.compare_exchange_weak(old,count,std::memory_order_relaxed)){}
  struct Leave { ~Leave(){active.fetch_sub(1,std::memory_order_relaxed);} } leave;
  delegate(); // Exactly one original call; exceptions propagate with RAII unlock.
  completed[api].fetch_add(1,std::memory_order_relaxed);
}
} // namespace mc2::host::input_call_gate
