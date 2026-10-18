#include "input_serialization.h"
#include <cassert>
#include <cstddef>
#include <rex/input/input.h>
#include <thread>
#include <vector>
using namespace mc2::host;
using namespace mc2::host::input_serialization;
std::atomic<unsigned> count{0};
void Delegate(PPCContext& ctx,uint8_t* memory) {
 assert(GetLastError()==0x1234 && errno==EAGAIN);
 ++count;ctx.r3.u64+=1;ctx.r4.u64^=0x11223344;memory[0]^=0x5a;
 errno=ERANGE;SetLastError(0x5678);
}
void Throws(PPCContext&,uint8_t*){throw 42;}
std::vector<uint8_t> Image() {
  std::vector<uint8_t> v(0x4000);
  auto* d=reinterpret_cast<IMAGE_DOS_HEADER*>(v.data());d->e_magic=IMAGE_DOS_SIGNATURE;d->e_lfanew=0x100;
  auto* n=reinterpret_cast<IMAGE_NT_HEADERS64*>(v.data()+0x100);
  n->Signature=IMAGE_NT_SIGNATURE;n->FileHeader.Machine=IMAGE_FILE_MACHINE_AMD64;
  n->FileHeader.SizeOfOptionalHeader=sizeof(IMAGE_OPTIONAL_HEADER64);
  n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR64_MAGIC;n->OptionalHeader.SizeOfImage=uint32_t(v.size());
  n->OptionalHeader.NumberOfRvaAndSizes=IMAGE_NUMBEROF_DIRECTORY_ENTRIES;
  n->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT]={0x300,2*sizeof(IMAGE_IMPORT_DESCRIPTOR)};
  auto* imp=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(v.data()+0x300);
  imp->Name=0x500;imp->OriginalFirstThunk=0x1000;imp->FirstThunk=0x1100;
  std::strcpy(reinterpret_cast<char*>(v.data()+0x500),"rexruntime.dll");
  for(size_t i=0;i<kCount;++i) {
    auto at=0x700+i*0x80;
    std::strcpy(reinterpret_cast<char*>(v.data()+at+2),kNames[i]);
    reinterpret_cast<uint64_t*>(v.data()+0x1000)[i]=at;
    reinterpret_cast<void**>(v.data()+0x1100)[i]=reinterpret_cast<void*>(original[i]);
  }
  return v;
}
// Verify the pinned SDK ABI independently of native Windows XINPUT layouts.
void InputLayout() {
 using namespace rex::input;
 static_assert(sizeof(void*)==8 && sizeof(PPCRegister)==8 && alignof(PPCContext)==64);
 static_assert(sizeof(X_INPUT_STATE)==16 && offsetof(X_INPUT_STATE,gamepad)==4);
 static_assert(sizeof(X_INPUT_GAMEPAD)==12 && offsetof(X_INPUT_GAMEPAD,thumb_lx)==4);
 static_assert(sizeof(X_INPUT_CAPABILITIES)==20 && offsetof(X_INPUT_CAPABILITIES,gamepad)==4 && offsetof(X_INPUT_CAPABILITIES,vibration)==16);
 static_assert(sizeof(X_INPUT_KEYSTROKE)==8 && offsetof(X_INPUT_KEYSTROKE,user_index)==6);
 static_assert(sizeof(X_INPUT_VIBRATION)==4);
 X_INPUT_STATE state{};state.packet_number=0x12345678;state.gamepad.buttons=0x9010;
 state.gamepad.left_trigger=0xAB;state.gamepad.right_trigger=0xCD;
 state.gamepad.thumb_lx=-2;state.gamepad.thumb_ly=0x1234;state.gamepad.thumb_rx=-32768;state.gamepad.thumb_ry=32767;
 const uint8_t expected[]={0x12,0x34,0x56,0x78,0x90,0x10,0xAB,0xCD,0xFF,0xFE,0x12,0x34,0x80,0x00,0x7F,0xFF};
 assert(std::memcmp(&state,expected,sizeof(expected))==0);
 std::puts("INPUT_ABI pointer_bits=64 register_bits=64 context_alignment=64 state_bytes=16 caps_bytes=20 keystroke_bytes=8 endian=BE offsets=verified");
}
int main(){
 InputLayout();
 original.fill(&Delegate);assert(!InstallInputSerialization(nullptr,nullptr,false));
 for(size_t api=0;api<4;++api){PPCContext a{},b{};a.r3.u64=0x100000020ull;a.r4.u64=0xFEDCBA9876543210ull;
 a.r1.u64=0x1234567800001000ull;a.r31.u64=0x8877665544332211ull;
 a.lr=0x1234567887654321ull;a.ctr.u64=0xFEDCBA9876543210ull;
 a.cr6.set_raw(0xB);a.xer.ca=1;a.f31.u64=0x7FF0000000000001ull;b=a;uint8_t ma=0,mb=0;
 errno=EAGAIN;SetLastError(0x1234);original[api](a,&ma);
 errno=EAGAIN;SetLastError(0x1234);wrappers[api](b,&mb);
 assert(std::memcmp(&a,&b,sizeof(a))==0 && ma==mb && errno==ERANGE && GetLastError()==0x5678);}
 std::vector<std::thread> threads;
 for(unsigned t=0;t<8;++t)threads.emplace_back([t]{for(unsigned n=0;n<1000;++n){PPCContext c{};uint8_t m=0;errno=EAGAIN;SetLastError(0x1234);wrappers[t%4](c,&m);assert(c.r3.u64==1 && m==0x5a && errno==ERANGE && GetLastError()==0x5678);}});
 for(auto& t:threads)t.join();assert(count==8008 && input_call_gate::peak==1 && input_call_gate::active==0);
 original[0]=&Throws;PPCContext c{};uint8_t m=0;try{wrappers[0](c,&m);assert(false);}catch(int e){assert(e==42);}assert(input_call_gate::active==0);original[0]=&Delegate;
 auto good=Image();std::array<void**,kCount> found{};assert(Plan(good.data(),good.size(),original,found));
 {auto absent=good;reinterpret_cast<uint64_t*>(absent.data()+0x1000)[3]=0;reinterpret_cast<void**>(absent.data()+0x1100)[3]=nullptr;assert(Plan(absent.data(),absent.size(),original,found) && !found[3]);}
 for(int bad=0;bad<9;++bad){auto bytes=good;auto* n=reinterpret_cast<IMAGE_NT_HEADERS64*>(bytes.data()+0x100);auto* imp=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(bytes.data()+0x300);
 if(bad==0)n->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;
 if(bad==1)n->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;
 if(bad==2)std::strcpy(reinterpret_cast<char*>(bytes.data()+0x500),"wrong.dll");
 if(bad==3)reinterpret_cast<uint64_t*>(bytes.data()+0x1000)[0]=0x780;
 if(bad==4)reinterpret_cast<void**>(bytes.data()+0x1100)[0]=nullptr;
 if(bad==5)imp->OriginalFirstThunk=0;
 if(bad==6)imp->FirstThunk=0x3FFC;
 if(bad==7)n->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].Size=sizeof(IMAGE_IMPORT_DESCRIPTOR);
 if(bad==8)n->OptionalHeader.SizeOfImage=0x5000;
 auto before=bytes;assert(!Plan(bytes.data(),bytes.size(),original,found));assert(bytes==before);}
 auto* page=static_cast<void**>(VirtualAlloc(nullptr,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));assert(page);page[0]=reinterpret_cast<void*>(original[0]);DWORD old;
 assert(VirtualProtect(page,4096,PAGE_READONLY,&old));assert(Exchange(page,reinterpret_cast<void*>(original[0]),reinterpret_cast<void*>(wrappers[0])));
 slots.fill(nullptr);slots[0]=page;slot_protection[0]=PAGE_READONLY;assert(RestoreInputSerializationBeforeGuest());assert(page[0]==reinterpret_cast<void*>(original[0]));
 MEMORY_BASIC_INFORMATION info{};VirtualQuery(page,&info,sizeof(info));assert(info.Protect==PAGE_READONLY);
 assert(VirtualProtect(page,4096,PAGE_READWRITE,&old));page[0]=reinterpret_cast<void*>(uintptr_t(123));assert(!RestoreInputSerializationBeforeGuest());assert(page[0]==reinterpret_cast<void*>(uintptr_t(123)));slots.fill(nullptr);VirtualFree(page,0,MEM_RELEASE);
 std::puts("INPUT_GATE_FIXTURE delegates=8008 peak=1 guards=9 exception_unlock=1 actual_restore=1");
}
