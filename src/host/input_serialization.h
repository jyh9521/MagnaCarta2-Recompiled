#pragma once
// Process-local IAT mitigation for the pinned SDK InputSystem refresh race.
// Install before guest launch. Runtime rollback is a new process with flag off.
#include <Windows.h>
#include <rex/ppc/context.h>
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include "input_call_gate.h"
namespace mc2::host {
namespace input_serialization {
inline constexpr size_t kCount=4;
inline constexpr std::array<const char*,kCount> kNames={
 "__imp__XamInputGetCapabilities","__imp__XamInputGetState",
 "__imp__XamInputSetState","__imp__XamInputGetKeystroke"};
inline std::array<PPCFunc*,kCount> original{};
inline std::array<void**,kCount> slots{};
inline std::array<DWORD,kCount> slot_protection{};
inline bool installed=false,used=false;
inline std::atomic<const char*> status{"disabled"};
inline uintptr_t module_base=0;
inline size_t module_size=0;
template<size_t Api> inline void Invoke(PPCContext& ctx,uint8_t* base) {
 const DWORD before_error=GetLastError();const int before_errno=errno;
 DWORD after_error=before_error;int after_errno=before_errno;
 input_call_gate::Invoke(Api,[&]{
   errno=before_errno;SetLastError(before_error);
   original[Api](ctx,base);
   after_error=GetLastError();after_errno=errno;
 });
 errno=after_errno;SetLastError(after_error);
}
inline const std::array<PPCFunc*,kCount> wrappers={&Invoke<0>,&Invoke<1>,&Invoke<2>,&Invoke<3>};
// Parser is independently mockable: bytes are a mapped AMD64 PE image, not raw
// file offsets. Every selected IAT slot is checked before any page write.
inline bool Plan(uint8_t* image, size_t extent, const std::array<PPCFunc*,kCount>& expected,
                 std::array<void**,kCount>& selected) {
  auto fits=[extent](uint64_t at,uint64_t size){return at<=extent && size<=extent-at;};
  if (!image || !fits(0,sizeof(IMAGE_DOS_HEADER))) return false;
  auto* dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);
  if (dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0 ||
      !fits(uint32_t(dos->e_lfanew),sizeof(IMAGE_NT_HEADERS64))) return false;
  auto* nt=reinterpret_cast<IMAGE_NT_HEADERS64*>(image+dos->e_lfanew);
  if (nt->Signature!=IMAGE_NT_SIGNATURE || nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_AMD64 ||
      nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC ||
      nt->FileHeader.SizeOfOptionalHeader!=sizeof(IMAGE_OPTIONAL_HEADER64) ||
      nt->OptionalHeader.SizeOfImage!=extent ||
      nt->OptionalHeader.NumberOfRvaAndSizes<=IMAGE_DIRECTORY_ENTRY_IMPORT) return false;
  const auto dir=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
  if (!dir.VirtualAddress || !fits(dir.VirtualAddress,dir.Size)) return false;
  auto string_at=[&](uint32_t at)->const char* {
    if (!fits(at,1)) return nullptr;
    const auto* p=reinterpret_cast<const char*>(image+at);
    return std::memchr(p,0,extent-at)?p:nullptr;
  };
  std::array<size_t,kCount> counts{}; selected.fill(nullptr);
  size_t matching_dlls=0; bool terminated=false;
  for (uint64_t at=dir.VirtualAddress; fits(at,sizeof(IMAGE_IMPORT_DESCRIPTOR)) &&
       at+sizeof(IMAGE_IMPORT_DESCRIPTOR)<=uint64_t(dir.VirtualAddress)+dir.Size;
       at+=sizeof(IMAGE_IMPORT_DESCRIPTOR)) {
    auto* d=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(image+at);
    if (!d->Name && !d->FirstThunk && !d->OriginalFirstThunk) {terminated=true;break;}
    const char* dll=string_at(d->Name); if (!dll) return false;
    if (_stricmp(dll,"rexruntime.dll")) continue;
    if (++matching_dlls!=1 || !d->OriginalFirstThunk || !d->FirstThunk) return false;
    bool thunk_end=false;
    for (uint64_t i=0; i<extent/sizeof(IMAGE_THUNK_DATA64);++i) {
      const uint64_t oa=uint64_t(d->OriginalFirstThunk)+i*8, ia=uint64_t(d->FirstThunk)+i*8;
      if (!fits(oa,8) || !fits(ia,8) || (ia&7)) return false;
      const uint64_t name=reinterpret_cast<IMAGE_THUNK_DATA64*>(image+oa)->u1.AddressOfData;
      if (!name) {thunk_end=true;break;}
      if (IMAGE_SNAP_BY_ORDINAL64(name)) continue;
      if (name>UINT32_MAX-2 || !fits(name,3)) return false;
      const char* symbol=string_at(uint32_t(name)+2); if (!symbol) return false;
      for (size_t n=0;n<kCount;++n) if (!std::strcmp(symbol,kNames[n])) {
        if (++counts[n]!=1 || !expected[n]) return false;
        void** slot=reinterpret_cast<void**>(image+ia);
        if (*slot!=reinterpret_cast<void*>(expected[n])) return false;
        selected[n]=slot;
      }
    }
    if (!thunk_end) return false;
  }
  if (!terminated || matching_dlls!=1) return false;
  // The pinned game imports three APIs. Keystroke is optional only when absent;
  // if imported it receives the identical shared gate. No required API is optional.
  for (size_t n=0;n<kCount;++n) if (n<3 ? counts[n]!=1 : counts[n]>1) return false;
  return true;
}

inline bool Exchange(void** slot, void* before, void* after) {
  DWORD protect=0;
  if (!VirtualProtect(slot,sizeof(void*),PAGE_READWRITE,&protect)) return false;
  void* observed=InterlockedCompareExchangePointer(slot,after,before);
  DWORD ignored=0; const bool protection_restored=VirtualProtect(slot,sizeof(void*),protect,&ignored)!=FALSE;
  return observed==before && *slot==after && protection_restored;
}
}  // namespace input_serialization

inline bool RestoreInputSerializationBeforeGuest() {
  using namespace input_serialization;
  bool okay=true;
  for (size_t n=0;n<kCount;++n) if (slots[n]) {
    const bool owned=*slots[n]==reinterpret_cast<void*>(wrappers[n]) ||
                     *slots[n]==reinterpret_cast<void*>(original[n]);
    if (*slots[n]==reinterpret_cast<void*>(wrappers[n]))
      okay=Exchange(slots[n],reinterpret_cast<void*>(wrappers[n]),reinterpret_cast<void*>(original[n]))&&okay;
    else okay=(*slots[n]==reinterpret_cast<void*>(original[n]))&&okay;
    // Preserve the preflight protection even if an earlier write succeeded but
    // its first protection-restoration call failed. Never claim that as clean.
    if (owned && slot_protection[n]) {
      DWORD ignored=0;MEMORY_BASIC_INFORMATION info{};
      const bool changed=VirtualProtect(slots[n],sizeof(void*),slot_protection[n],&ignored)!=FALSE;
      const bool queried=VirtualQuery(slots[n],&info,sizeof(info))==sizeof(info);
      okay=changed && queried && info.Protect==slot_protection[n] && okay;
    }
  }
  installed=false; status=okay?"restored":"restore-failed";
  return okay;
}

// Caller attests the loaded runtime's complete SHA above. Install before guest
// threads start, never on a running module. Only the current EXE's IAT is owned.
inline bool InstallInputSerialization(HMODULE exe, HMODULE runtime, bool verified) {
  using namespace input_serialization;
  if (!verified) {status="unsupported-sdk";return false;}
  if (installed || used) {status="already-used";return false;}
  if (!exe || exe!=GetModuleHandleW(nullptr) || !runtime ||
      runtime!=GetModuleHandleW(L"rexruntime.dll")) {status="module-mismatch";return false;}
  for (size_t n=0;n<kCount;++n) {
    original[n]=reinterpret_cast<PPCFunc*>(GetProcAddress(runtime,kNames[n]));
    if (!original[n]) {status="missing-export";return false;}
  }
  auto* base=reinterpret_cast<uint8_t*>(exe);
  auto* dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
  auto* nt=reinterpret_cast<IMAGE_NT_HEADERS64*>(base+dos->e_lfanew);
  if (!Plan(base,nt->OptionalHeader.SizeOfImage,original,slots)) {status="import-guard-failed";return false;}
  for (size_t n=0;n<kCount;++n) {
    if (!slots[n]) continue;
    MEMORY_BASIC_INFORMATION info{};
    if (VirtualQuery(slots[n],&info,sizeof(info))!=sizeof(info) || info.State!=MEM_COMMIT ||
        (info.Protect&(PAGE_GUARD|PAGE_NOACCESS))) {status="iat-page-guard-failed";return false;}
    slot_protection[n]=info.Protect;
  }
  module_base=uintptr_t(base);module_size=nt->OptionalHeader.SizeOfImage;
  for (size_t n=0;n<kCount;++n) {
    if (!slots[n]) continue;
    if (!Exchange(slots[n],reinterpret_cast<void*>(original[n]),reinterpret_cast<void*>(wrappers[n]))) {
      RestoreInputSerializationBeforeGuest();status="install-failed-rollback-attempted";return false;
    }
  }
  installed=true;used=true;status="installed";
  std::printf("INPUT_SERIALIZATION_SCOPE required=3 keystroke_imported=%u\n",unsigned(slots[3]!=nullptr));return true;
}


inline void DumpInputSerialization(FILE* output=stdout) {
 using namespace input_serialization;
 std::fprintf(output,"INPUT_SERIALIZATION status=%s installed=%u active=%llu peak=%llu scope=host_four_input_imports\n",
   status.load(),unsigned(installed),(unsigned long long)input_call_gate::active.load(),(unsigned long long)input_call_gate::peak.load());
 for(size_t n=0;n<kCount;++n)std::fprintf(output,"INPUT_SERIALIZATION_API api=%s calls=%llu completed=%llu\n",kNames[n],
   (unsigned long long)input_call_gate::calls[n].load(),(unsigned long long)input_call_gate::completed[n].load());
}
} // namespace mc2::host
