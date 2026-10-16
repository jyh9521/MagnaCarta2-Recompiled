// Real SDK XEX loading; only call arguments / stack are synthetic. No original image data writes.
#include <rex/runtime.h>
#include <rex/kernel/init.h>
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
  const uint32_t fixture = memory->SystemHeapAlloc(0x10000);
  if (!fixture) return 11;
  const bool original_vtables = Read32(base, 0x8320B718)==kIntConst && Read32(base,0x8320B828)==kAdd;
  std::printf("IMAGE_VTABLE operand=%08X add=%08X original=%u\n", Read32(base,0x8320B718),Read32(base,0x8320B828),unsigned(original_vtables));
  if(!original_vtables) return 15;
  size_t original_zero=0; for(uint32_t i=0;i<4096;++i)if(Read32(base,kNatives+i*4)==0)++original_zero;
  std::printf("IMAGE_GNATIVES zero_slots=%zu\n",original_zero);
  if(original_zero!=4096)return 17;
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
  std::printf("NATIVE_ADD cases=%zu index=%u target=%08X operand=%08X fixture_released=1 status=%d\n",
      cases.size(), kAddIndex, kAdd, kIntConst, status);
  return status;
}

#include "mc2_probe_init.h"
#include <rex/system/user_module.h>
#include <filesystem>
#include <cstdlib>
#include <fstream>
#include <Windows.h>
extern void mc2_probe_RegisterFunctions(rex::runtime::IModuleRegistrar*);
int main() {
 try {
  char dll[MAX_PATH]{}; auto m=GetModuleHandleA("rexruntime.dll");
  if(!m || !GetModuleFileNameA(m,dll,MAX_PATH))return 8;
  std::printf("RUNTIME_DLL %s\n",dll);
  const char* input=std::getenv("MC2_XEX_PATH"); if(!input)return 9;
  const std::filesystem::path path(input);
  rex::Runtime runtime(path.parent_path(), "./user", {}, "./cache");
  rex::RuntimeConfig config; config.tool_mode=true;
  config.kernel_init=rex::kernel::InitializeKernel;
  auto status=runtime.Setup(PPCImageConfig,std::move(config));
  std::printf("SETUP status=%08X\n",unsigned(status)); std::fflush(stdout);
  if(status)return 2;
  mc2_probe_RegisterFunctions(runtime.function_dispatcher());
  size_t total=0; for(auto* f=PPCFuncMappings;f->host;++f) {
   if(runtime.function_dispatcher()->GetFunction(uint32_t(f->guest))!=f->host)return 4; ++total;
  }
  std::printf("REGISTRATION count=%zu base=mapped\n",total);
  const auto guest=std::string("game:\\")+path.filename().string();
  status=runtime.LoadXexImage(guest);
  std::printf("IMAGE_LOAD path=%s status=%08X\n",guest.c_str(),unsigned(status)); std::fflush(stdout);
  if(status)return 20;
  auto module=runtime.kernel_state()->GetExecutableModule();
  if(!module)return 21;
  std::printf("IMAGE_MODULE entry=%08X stack=%08X\n",module->entry_point(),module->stack_size());
  auto* base=runtime.virtual_membase();
  size_t variable_count=0;
  for(const auto& lib:*module->xex_module()->import_libraries())for(const auto& imp:lib.imports) {
   auto* exp=runtime.export_resolver()->GetExportByOrdinal(lib.name,static_cast<uint16_t>(imp.ordinal));
   if(exp && exp->type==rex::runtime::Export::Type::kVariable) {
    const auto actual=Read32(base,imp.value_address);
    std::printf("IMAGE_VARIABLE library=%s ordinal=%u slot=%08X actual=%08X expected=%08X success=%u\n",lib.name.c_str(),imp.ordinal,imp.value_address,actual,exp->variable_ptr,unsigned(actual==exp->variable_ptr));
    if(actual!=exp->variable_ptr)return 24; ++variable_count;
   }
  }
  std::printf("IMAGE_KERNEL tables=%zu variables=%zu\n",runtime.export_resolver()->tables().size(),variable_count);
  // Loaded memory snapshot remains ignored local evidence, taken before original initializers.
  const auto pe=*reinterpret_cast<const uint32_t*>(base+0x8200003C);
  const auto pe_size=*reinterpret_cast<const uint32_t*>(base+0x82000000+pe+24+56);
  const auto size=module->xex_module()->xex_security_info()->image_size;
  std::printf("IMAGE_SIZES security=%u pe_declared=%u sdk_pages=%u\n",size,pe_size,module->xex_module()->image_size());
  size_t imports=0; for(const auto& lib:*module->xex_module()->import_libraries()) { imports+=lib.imports.size(); std::printf("IMAGE_IMPORT library=%s records=%zu\n",lib.name.c_str(),lib.imports.size()); }
  if(size==0 || size>0x4000000)return 22;
  std::ofstream dump("loaded-image.bin",std::ios::binary);
  dump.write(reinterpret_cast<const char*>(base+0x82000000),size); dump.close();
  std::printf("IMAGE_SNAPSHOT base=82000000 size=%u\n",size);
  const int native=RunNativeAddProbe(runtime);
  std::printf("NATIVE_PROBE status=%d\n",native); std::fflush(stdout);
  if(native)return native;
  module.reset(); // Release host reference before kernel and memory teardown.
  runtime.Shutdown();std::puts("SHUTDOWN complete");
  return 0;
 }catch(const std::exception& e){std::fprintf(stderr,"IMAGE_EXCEPTION %s\n",e.what());return 23;}
}
