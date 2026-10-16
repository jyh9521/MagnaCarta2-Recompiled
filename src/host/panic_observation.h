#pragma once
// Bounded caller-gated guest byte observation. No game addresses or context writes.
// This does not establish a coherent snapshot or MMIO/fault-handler safety.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace mc2::host::panic_observation {

inline constexpr std::size_t kMaxUtf16Units = 4096;
inline constexpr std::size_t kMaxBytes = kMaxUtf16Units * 2;
inline constexpr std::uint64_t kGuestSpace = 0x100000000ULL;
inline constexpr std::uint64_t kMaxSpan = 0x100001000ULL;

struct GuestView {
  const void* base = nullptr;
  std::uint64_t span = 0;
};

enum class Status {
  ok, invalid_view, null_guest, invalid_count, guest_overflow, outside_span,
  host_overflow, query_failed, unreadable, partial_read, read_failed
};

inline const char* StatusName(Status status) noexcept {
  switch (status) {
    case Status::ok: return "ok";
    case Status::invalid_view: return "invalid-view";
    case Status::null_guest: return "null-guest";
    case Status::invalid_count: return "invalid-count";
    case Status::guest_overflow: return "guest-overflow";
    case Status::outside_span: return "outside-span";
    case Status::host_overflow: return "host-overflow";
    case Status::query_failed: return "query-failed";
    case Status::unreadable: return "unreadable";
    case Status::partial_read: return "partial-read";
    case Status::read_failed: return "read-failed";
  }
  return "unknown";
}

struct Result {
  Status status = Status::invalid_view;
  std::uint32_t guest = 0;
  std::size_t requested = 0;
  std::size_t captured = 0;
  bool readable = false;
  bool terminated = false;
  bool truncated = false;
  bool word_known = false;
  std::uint32_t word = 0;
  std::array<std::uint8_t, kMaxBytes> bytes{};
};

namespace detail {
inline std::uint64_t Bias(std::uint32_t guest) noexcept {
  return guest >= 0xE0000000U ? 0x1000ULL : 0ULL;
}

inline Status Validate(GuestView view, std::uint32_t guest,
                       std::size_t count) noexcept {
  if (!view.base || !view.span || view.span > kMaxSpan) return Status::invalid_view;
  if (!guest) return Status::null_guest;
  if (!count || count > kMaxBytes) return Status::invalid_count;
  const auto end = std::uint64_t(guest) + count;
  if (end > kGuestSpace) return Status::guest_overflow;
  const auto last = end - 1;
  const auto physical_last = last + Bias(static_cast<std::uint32_t>(last));
  if (physical_last >= view.span) return Status::outside_span;
  const auto start = reinterpret_cast<std::uintptr_t>(view.base);
  if (physical_last > std::numeric_limits<std::uintptr_t>::max() - start)
    return Status::host_overflow;
  return Status::ok;
}

inline bool ReadableProtection(DWORD protection) noexcept {
  if (protection & (PAGE_GUARD | PAGE_NOACCESS)) return false;
  switch (protection & 0xFFU) {
    case PAGE_READONLY: case PAGE_READWRITE: case PAGE_WRITECOPY:
    case PAGE_EXECUTE_READ: case PAGE_EXECUTE_READWRITE: case PAGE_EXECUTE_WRITECOPY:
      return true;
    default: return false;
  }
}

inline Status Preflight(std::uintptr_t address, std::size_t count) noexcept {
  std::size_t consumed = 0;
  while (consumed < count) {
    MEMORY_BASIC_INFORMATION info{};
    const auto current = address + consumed;
    if (VirtualQuery(reinterpret_cast<const void*>(current), &info, sizeof(info)) != sizeof(info))
      return Status::query_failed;
    const auto region = reinterpret_cast<std::uintptr_t>(info.BaseAddress);
    if (!info.RegionSize || region > current || info.RegionSize >
        std::numeric_limits<std::uintptr_t>::max() - region)
      return Status::unreadable;
    const auto end = region + info.RegionSize;
    if (end <= current || info.State != MEM_COMMIT || !ReadableProtection(info.Protect))
      return Status::unreadable;
    const auto available = end - current;
    consumed += available < count - consumed ? static_cast<std::size_t>(available) : count - consumed;
  }
  return Status::ok;
}

inline Status CopyStatus(BOOL copied, SIZE_T received, std::size_t expected) noexcept {
  if (received != expected) return received ? Status::partial_read : Status::read_failed;
  return copied ? Status::ok : Status::read_failed;
}

// Preflight every physical segment before any copy; do not consume PAGE_GUARD.
// RPM may still fail/partially copy if another thread changes the mapping.
inline Status Read(GuestView view, std::uint32_t guest, std::uint8_t* destination,
                   std::size_t count) noexcept {
  auto status = Validate(view, guest, count);
  if (status != Status::ok) return status;
  if (!destination) return Status::invalid_count;
  const auto base = reinterpret_cast<std::uintptr_t>(view.base);
  for (unsigned pass = 0; pass < 2; ++pass) {
    std::size_t consumed = 0;
    while (consumed < count) {
      const auto logical = std::uint64_t(guest) + consumed;
      std::size_t segment = count - consumed;
      if (logical < 0xE0000000ULL && logical + segment > 0xE0000000ULL)
        segment = static_cast<std::size_t>(0xE0000000ULL - logical);
      const auto address = base + logical + Bias(static_cast<std::uint32_t>(logical));
      if (pass == 0) {
        status = Preflight(address, segment);
        if (status != Status::ok) return status;
      } else {
        SIZE_T received = 0;
        const BOOL copied = ReadProcessMemory(GetCurrentProcess(),
            reinterpret_cast<const void*>(address), destination + consumed, segment, &received);
        status = CopyStatus(copied, received, segment);
        if (status != Status::ok) return status;
      }
      consumed += segment;
    }
  }
  return Status::ok;
}

inline void Fail(Result& result, Status status) noexcept {
  result.status = status;
  result.captured = 0;
  result.readable = result.terminated = result.truncated = result.word_known = false;
  result.word = 0;
  result.bytes.fill(0);
}
}  // namespace detail

inline Result ReadBytes(GuestView view, std::uint32_t guest,
                        std::size_t count) noexcept {
  Result result{};
  result.guest = guest;
  result.requested = count;
  const auto status = detail::Read(view, guest, result.bytes.data(), count);
  if (status != Status::ok) { detail::Fail(result, status); return result; }
  result.status = Status::ok;
  result.readable = true;
  result.captured = count;
  return result;
}

inline Result ReadWord(GuestView view, std::uint32_t guest) noexcept {
  auto result = ReadBytes(view, guest, 4);
  if (result.status == Status::ok) {
    result.word = (std::uint32_t(result.bytes[0]) << 24) |
                  (std::uint32_t(result.bytes[1]) << 16) |
                  (std::uint32_t(result.bytes[2]) << 8) | result.bytes[3];
    result.word_known = true;
  }
  return result;
}

// captured includes exactly one terminal 0000 unit if found. No Unicode repair,
// control-code rewriting, heap allocation, or read beyond that terminal unit.
inline Result ReadUtf16(GuestView view, std::uint32_t guest,
                        std::size_t max_units) noexcept {
  Result result{};
  result.guest = guest;
  if (!max_units || max_units > kMaxUtf16Units) {
    detail::Fail(result, Status::invalid_count);
    return result;
  }
  result.requested = max_units * 2;
  const auto range = detail::Validate(view, guest, result.requested);
  if (range != Status::ok) { detail::Fail(result, range); return result; }
  for (std::size_t unit = 0; unit < max_units; ++unit) {
    const auto position = unit * 2;
    const auto status = detail::Read(view, static_cast<std::uint32_t>(std::uint64_t(guest) + position),
                                     result.bytes.data() + position, 2);
    if (status != Status::ok) { detail::Fail(result, status); return result; }
    result.captured += 2;
    if (result.bytes[position] == 0 && result.bytes[position + 1] == 0) {
      result.status = Status::ok;
      result.readable = result.terminated = true;
      return result;
    }
  }
  result.status = Status::ok;
  result.readable = result.truncated = true;
  return result;
}

}  // namespace mc2::host::panic_observation
