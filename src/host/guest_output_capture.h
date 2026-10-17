#pragma once
// Public SDK guest-output readback only. No Paint/Refresh or guest/context writes.
#include <rex/ui/presenter.h>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>

namespace mc2::host::guest_output_capture {
inline constexpr std::size_t kMaxBytes = 256ULL * 1024 * 1024;
struct Stats {
  uint32_t width=0,height=0;
  std::size_t stride=0,data_bytes=0,rgb_bytes=0;
  uint64_t nonblack_pixels=0,varied_pixels=0;
};
inline bool ValidPath(const char* path) {
  if(!path || !*path)return false;
  for(const unsigned char* p=reinterpret_cast<const unsigned char*>(path);*p;++p)
    if(*p<=0x20 || *p==0x7f)return false; // Marker paths are one bounded caller-selected token.
  return true;
}
inline const char* ValidateRawImage(const rex::ui::RawImage& image,Stats& out) {
  out={};out.width=image.width;out.height=image.height;out.stride=image.stride;out.data_bytes=image.data.size();
  if(!image.width || !image.height || image.width>8192 || image.height>8192)return "dimensions-invalid";
  const std::size_t row=std::size_t(image.width)*4;
  if(image.stride<row)return "stride-invalid";
  if(image.data.size()>kMaxBytes)return "data-limit";
  const std::size_t rows=image.height-1;
  if(rows && image.stride>(std::numeric_limits<std::size_t>::max()-row)/rows)return "span-overflow";
  const std::size_t needed=rows*image.stride+row;
  if(needed>kMaxBytes)return "span-limit";
  if(needed>image.data.size())return "data-short";
  out.rgb_bytes=std::size_t(image.width)*std::size_t(image.height)*3;
  const auto* first=image.data.data();
  for(uint32_t y=0;y<image.height;++y) {
    const auto* pixels=image.data.data()+std::size_t(y)*image.stride;
    for(uint32_t x=0;x<image.width;++x) {
      const auto* p=pixels+std::size_t(x)*4;
      out.nonblack_pixels+=bool(p[0]||p[1]||p[2]);
      out.varied_pixels+=bool(p[0]!=first[0]||p[1]!=first[1]||p[2]!=first[2]);
    }
  }
  return "valid";
}
// Internal encoder: caller has validated the image and owns file closure.
inline bool WriteValidatedRows(FILE* file,const rex::ui::RawImage& image) {
  if(!file)return false;
  std::array<uint8_t,8192*3> rgb{};
  const std::size_t row_bytes=std::size_t(image.width)*3;
  bool okay=std::fprintf(file,"P6\n%u %u\n255\n",image.width,image.height)>0;
  for(uint32_t y=0;okay && y<image.height;++y) {
    const auto* source=image.data.data()+std::size_t(y)*image.stride;
    for(uint32_t x=0;x<image.width;++x)
      for(unsigned c=0;c<3;++c)rgb[std::size_t(x)*3+c]=source[std::size_t(x)*4+c];
    okay=std::fwrite(rgb.data(),1,row_bytes,file)==row_bytes;
  }
  return okay && std::ferror(file)==0;
}
inline const char* WriteRawImagePPM(const rex::ui::RawImage& image,const char* path,Stats& out) {
  const char* status=ValidateRawImage(image,out);
  if(std::strcmp(status,"valid")!=0)return status;
  if(!ValidPath(path))return "path-invalid";
  FILE* file=std::fopen(path,"wb");
  if(!file)return "file-open-failed";
  const bool okay=WriteValidatedRows(file,image);
  const int close_status=std::fclose(file);
  if(!okay)return "file-write-failed";
  if(close_status!=0)return "file-close-failed";
  return "captured";
}
inline bool Report(const char* path,const char* status,const Stats& stats,bool sdk_readback) {
  std::printf("GUEST_OUTPUT_CAPTURE requested=1 status=%s path=%s width=%u height=%u stride=%zu data_bytes=%zu rgb_bytes=%zu nonblack_pixels=%llu varied_pixels=%llu sdk_readback=%u\n",
    status,ValidPath(path)?path:"-",stats.width,stats.height,stats.stride,stats.data_bytes,stats.rgb_bytes,
    static_cast<unsigned long long>(stats.nonblack_pixels),static_cast<unsigned long long>(stats.varied_pixels),unsigned(sdk_readback));
  return std::strcmp(status,"captured")==0;
}
} // namespace mc2::host::guest_output_capture

namespace mc2::host {
inline bool CaptureGuestOutput(rex::ui::Presenter* presenter,const char* path) {
  namespace capture=guest_output_capture;
  capture::Stats stats{};
  if(!capture::ValidPath(path))return capture::Report(path,"path-invalid",stats,false);
  if(!presenter)return capture::Report(path,"presenter-null",stats,false);
  rex::ui::RawImage image;
  // Exactly one public SDK capture call. Exceptions/fatal behavior are not repaired.
  if(!presenter->CaptureGuestOutput(image))return capture::Report(path,"sdk-readback-failed",stats,false);
  const char* status=capture::WriteRawImagePPM(image,path,stats);
  return capture::Report(path,status,stats,true);
}
} // namespace mc2::host
