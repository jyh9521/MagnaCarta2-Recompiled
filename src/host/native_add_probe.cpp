// Controlled guest-memory fixture; all called implementations are original generated code.
#include <rex/runtime.h>
#include <rex/system/function_dispatcher.h>
#include <rex/system/xmemory.h>
#include <rex/ppc.h>
#include <array>
#include <cstdio>
#include <cstring>

namespace {
constexpr uint32_t kNatives = 0x83250D80;
constexpr uint32_t kAddIndex = 146;
constexpr uint32_t kAdd = 0x8250BAF0;
constexpr uint32_t kIntConst = 0x82508E60;
void Write32(uint8_t* base, uint32_t address, uint32_t value) {
  value = __builtin_bswap32(value);
  std::memcpy(base + address, &value, sizeof(value));
}
uint32_t Read32(uint8_t* base, uint32_t address) {
  uint32_t value;
  std::memcpy(&value, base + address, sizeof(value));
  return __builtin_bswap32(value);
}
}

int RunNativeAddProbe(rex::Runtime& runtime) {
  auto* memory = runtime.memory();
  auto* base = runtime.virtual_membase();
  auto* heap = memory->LookupHeap(kNatives);
  if (!heap || !heap->AllocFixed(0x83250000, 0x30000, 0x10000,
      rex::memory::kMemoryAllocationReserve | rex::memory::kMemoryAllocationCommit,
      rex::memory::kMemoryProtectRead | rex::memory::kMemoryProtectWrite)) return 10;
  if (!heap->AllocFixed(0x83200000, 0x10000, 0x10000,
      rex::memory::kMemoryAllocationReserve | rex::memory::kMemoryAllocationCommit,
      rex::memory::kMemoryProtectRead | rex::memory::kMemoryProtectWrite)) {
    heap->Release(0x83250000); return 15;
  }
  const uint32_t fixture = memory->SystemHeapAlloc(0x10000);
  if (!fixture) { heap->Release(0x83250000); heap->Release(0x83200000); return 11; }
  // Reproduce two hash-verified original static vtable data words, NOT GNatives slots.
  Write32(base, 0x8320B718, kIntConst);
  Write32(base, 0x8320B828, kAdd);
  PPCContext init{};
  auto* dispatcher = runtime.function_dispatcher();
  dispatcher->GetFunction(0x82E707C8)(init, base);  // Real IntConst registration + fallback fill.
  dispatcher->GetFunction(0x82E73108)(init, base);  // Real Add_IntInt registration; guard prevents refill.
  const bool initial_bindings = Read32(base, kNatives + 0x1D * 4) == kIntConst &&
    Read32(base, kNatives + kAddIndex * 4) == kAdd && Read32(base, 0x8327B660) == 1;
  dispatcher->GetFunction(0x82E707C8)(init, base);  // Real duplicate registration path.
  size_t fallback_slots = 0;
  for (uint32_t slot = 0; slot < 4096; ++slot) {
    if (Read32(base, kNatives + slot * 4) == 0x82505980) ++fallback_slots;
  }
  const bool initializer_okay = initial_bindings && fallback_slots == 4094 &&
    Read32(base, 0x83263F1C) == 29;
  std::printf("NATIVE_INITIALIZERS operand=82E707C8 add=82E73108 guard=%u fallback_slots=%zu duplicate_index=%u success=%u\n",
    Read32(base, 0x8327B660), fallback_slots, Read32(base, 0x83263F1C), unsigned(initializer_okay));
  const uint32_t frame = fixture + 0x100;
  const uint32_t script = fixture + 0x200;
  const uint32_t result = fixture + 0x300;
  const uint32_t stack = fixture + 0xF000;
  constexpr std::array<std::array<uint32_t, 2>, 8> cases{{
    {7, 35}, {0, 0}, {0xFFFFFFFF, 1}, {0x80000000, 0xFFFFFFFF},
    {0x7FFFFFFF, 1}, {0xFFFFFFFE, 0xFFFFFFFD}, {0x12345678, 0x11111111},
    {0x80000000, 0x80000000}}};
  int status = initializer_okay ? 0 : 16;
  for (size_t i = 0; i < cases.size() && initializer_okay; ++i) {
    std::memset(base + fixture, 0, 0x10000);
    base[script] = 0x1D;
    Write32(base, script + 1, cases[i][0]);
    base[script + 5] = 0x1D;
    Write32(base, script + 6, cases[i][1]);
    base[script + 10] = 0x16;  // EndFunctionParms.
    base[script + 11] = 0x53;  // EndOfScript; no optional DebugInfo.
    Write32(base, frame + 12, script);
    Write32(base, result - 4, 0xA1B2C3D4);
    Write32(base, result, 0xDEADBEEF);
    Write32(base, result + 4, 0xB1C2D3E4);
    PPCContext ctx{};
    ctx.r1.u32 = stack;
    ctx.r3.u32 = 0;
    ctx.r4.u32 = frame;
    ctx.r5.u32 = result;
    ctx.lr = 0x12345678;
    ctx.r28.u64 = 0x1020304050607080;
    ctx.r29.u64 = 0x1122334455667788;
    ctx.r30.u64 = 0x8877665544332211;
    ctx.r31.u64 = 0x8070605040302010;
    const uint32_t target = Read32(base, kNatives + kAddIndex * 4);
    auto* function = runtime.function_dispatcher()->GetFunction(target);
    if (!function || target != kAdd) { status = 12; break; }
    function(ctx, base);
    const uint32_t actual = Read32(base, result);
    const uint32_t expected = cases[i][0] + cases[i][1];
    const uint32_t consumed = Read32(base, frame + 12) - script;
    const bool restored = ctx.r1.u32 == stack && ctx.lr == 0x12345678 &&
      ctx.r28.u64 == 0x1020304050607080 && ctx.r29.u64 == 0x1122334455667788 &&
      ctx.r30.u64 == 0x8877665544332211 && ctx.r31.u64 == 0x8070605040302010;
    const bool guards = Read32(base, result - 4) == 0xA1B2C3D4 &&
      Read32(base, result + 4) == 0xB1C2D3E4;
    const bool unchanged = base[script] == 0x1D && base[script + 5] == 0x1D &&
      Read32(base, script + 1) == cases[i][0] && Read32(base, script + 6) == cases[i][1] &&
      base[script + 10] == 0x16 && base[script + 11] == 0x53;
    const bool okay = actual == expected && consumed == 11 && restored && guards && unchanged;
    std::printf("NATIVE_CASE %zu lhs=%08X rhs=%08X result=%08X code_advance=%u restored=%u guards=%u script_unchanged=%u success=%u\n",
      i, cases[i][0], cases[i][1], actual, consumed, unsigned(restored), unsigned(guards), unsigned(unchanged), unsigned(okay));
    if (!okay) status = 13;
  }
  memory->SystemHeapFree(fixture);
  const bool released_native = heap->Release(0x83250000);
  const bool released_static = heap->Release(0x83200000);
  const bool released = released_native && released_static;
  std::printf("NATIVE_ADD cases=%zu index=%u target=%08X operand=%08X fixture_released=%u status=%d\n",
      cases.size(), kAddIndex, kAdd, kIntConst, unsigned(released), status);
  return status ? status : released ? 0 : 14;
}
