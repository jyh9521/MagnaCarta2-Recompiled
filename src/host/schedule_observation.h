#pragma once
// Read-only, original-caller-gated schedule samples. Not atomic snapshots.
#include "schedule_import_trace.h"
#include "panic_observation.h"
namespace mc2::host::schedule_observation {
namespace po=panic_observation;
inline bool DataRange(uint64_t address,size_t count) {
  const uint64_t end=address+count;
  return count && end>=address && ((address>=0x10000 && end<=0x7F000000ULL) ||
      (address>=0x82000000 && end<=0x83330000ULL));
}
inline bool Read(po::GuestView view,uint64_t address,size_t count,uint64_t& out) {
  if(!DataRange(address,count) || count>8)return false;
  const auto value=po::ReadBytes(view,uint32_t(address),count);
  if(value.status!=po::Status::ok || value.captured!=count)return false;
  uint64_t word=0;for(size_t i=0;i<count;++i)word=(word<<8)|value.bytes[i];out=word;return true;
}
inline bool OriginalBytes(po::GuestView view) {
  // Exact complete delay/wait/tail bodies, independently verified from pinned XEX.
  static constexpr uint32_t guards[][2]={
    {0x82869800,0x7D8802A6},
    {0x82869804,0x9181FFF8},
    {0x82869808,0xFBC1FFE8},
    {0x8286980C,0xFBE1FFF0},
    {0x82869810,0x9421FF90},
    {0x82869814,0x7C9F2378},
    {0x82869818,0x2F03FFFF},
    {0x8286981C,0x419A0014},
    {0x82869820,0x786B0020},
    {0x82869824,0x1D6BD8F0},
    {0x82869828,0xF9610050},
    {0x8286982C,0x48000014},
    {0x82869830,0x39600000},
    {0x82869834,0x3D408000},
    {0x82869838,0x91610054},
    {0x8286983C,0x91410050},
    {0x82869840,0x57FE063E},
    {0x82869844,0x38A10050},
    {0x82869848,0x7FE4FB78},
    {0x8286984C,0x38600001},
    {0x82869850,0x486246FD},
    {0x82869854,0x2B1E0000},
    {0x82869858,0x419A000C},
    {0x8286985C,0x2F030101},
    {0x82869860,0x419AFFE4},
    {0x82869864,0x3963FF40},
    {0x82869868,0x394000C0},
    {0x8286986C,0x316BFFFF},
    {0x82869870,0x7D6B5910},
    {0x82869874,0x7D635038},
    {0x82869878,0x38210070},
    {0x8286987C,0x8181FFF8},
    {0x82869880,0x7D8803A6},
    {0x82869884,0xEBC1FFE8},
    {0x82869888,0xEBE1FFF0},
    {0x8286988C,0x4E800020},
    {0x82399778,0x7D8802A6},
    {0x8239977C,0x484D5CA1},
    {0x82399780,0x9421FF80},
    {0x82399784,0x7C7F1B78},
    {0x82399788,0x38610050},
    {0x8239978C,0x7C9E2378},
    {0x82399790,0x484CE781},
    {0x82399794,0x817F0000},
    {0x82399798,0x7F0BF040},
    {0x8239979C,0xEBA10050},
    {0x823997A0,0x40990018},
    {0x823997A4,0x38600000},
    {0x823997A8,0x484CED19},
    {0x823997AC,0x817F0000},
    {0x823997B0,0x7F0BF040},
    {0x823997B4,0x4199FFF0},
    {0x823997B8,0x38610050},
    {0x823997BC,0x484CE755},
    {0x823997C0,0x3D208326},
    {0x823997C4,0xE8E10050},
    {0x823997C8,0x7D5D3850},
    {0x823997CC,0x81693B00},
    {0x823997D0,0x7D6A5A14},
    {0x823997D4,0x91693B00},
    {0x823997D8,0x38210080},
    {0x823997DC,0x484D5C90},
    {0x828684C0,0x38800000},
    {0x828684C4,0x4800133C},
    {0x8286F41C,0xFBA1FFE0},
    {0x8286F420,0xFBC1FFE8},
    {0x8286F424,0xFBE1FFF0},
    {0x8286F428,0x9181FFF8},
    {0x8286F42C,0x4E800020},
    {0x82E207F8,0x387D0028},
    {0x82E207FC,0x4B578E55},
    {0x82E20800,0x38800001},
    {0x82E20804,0x387D0028},
    {0x82E20808,0x4B578F71},
  };
  for(const auto& guard:guards){uint64_t got=0;if(!Read(view,guard[0],4,got) || got!=guard[1])return false;}
  return true;
}
inline ScheduleExtra Sample(uint32_t api,const PPCContext& c,uint8_t* base) {
  ScheduleExtra x{};po::GuestView view{base,0x100001000ULL};
  auto field=[&](unsigned slot,uint64_t address,size_t count){if(Read(view,address,count,x.values[slot]))x.flags|=uint32_t(1)<<slot;};
  // x5 is a raw global word, NOT proof of its class, lifetime or producer.
  field(5,0x83263ACC,4);x.values[6]=c.r29.u64;
  if(api==0 && c.lr==0x82869854) {
    field(0,c.r5.u32,8);field(1,uint64_t(c.r1.u32)+0x68,4);
    if((x.flags&2) && x.values[1]==0x823997AC) {
      field(2,uint64_t(c.r1.u32)+0x60,8);field(3,uint64_t(c.r1.u32)+0x58,8);
      field(7,uint64_t(c.r1.u32)+0xE8,4); // poll entry saved LR, not a 64-bit slot
      if(x.flags&4)field(4,uint32_t(x.values[2]),4);
    }
  } else if(api==1 || api==2) {
    // Raw SDK structure fields only; owner_token is not a public thread ID.
    field(0,uint64_t(c.r3.u32)+0x10,4);field(1,uint64_t(c.r3.u32)+0x14,4);
    field(2,uint64_t(c.r3.u32)+0x18,4);
  }
  return x;
}
} // namespace mc2::host::schedule_observation
