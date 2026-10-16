#include "presentation_probe.h"
#include <rex/cvar.h>
#include <rex/logging.h>
#include <rex/system/gpu_plugin.h>
#include <chrono>
#include <cstdlib>
#include <thread>

int main(int argc, char** argv) {
  SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
  std::setvbuf(stdout, nullptr, _IONBF, 0);
  std::setvbuf(stderr, nullptr, _IONBF, 0);
  const char* text = std::getenv("MC2_PRESENTER_MS");
  char* end = nullptr;
  const unsigned duration = text ? unsigned(std::strtoul(text, &end, 10)) : 500;
  if ((text && (!*text || !end || *end)) || duration < 100 || duration > 5000) return 10;
  rex::cvar::Init(argc, argv);
  rex::cvar::ApplyEnvironment();
  rex::LogConfig logging;
  logging.log_file = "presenter-sdk.log";
  logging.default_level = spdlog::level::debug;
  logging.flush_level = spdlog::level::debug;
  rex::InitLogging(logging);
  std::puts("PRESENTER_SCOPE xex_loaded=0 guest_gpu_setup=0 game_assets=0");

  // Session outlives graphics: the SDL context must survive backend cleanup.
  mc2::host::PresentationSession session;
  const auto plugin = LoadLibraryW(L"rexgpu-xenos.dll");
  if (!plugin) return 11;
  auto version = reinterpret_cast<rex::system::GpuAbiVersionFn>(
      GetProcAddress(plugin, rex::system::kGpuAbiVersionSymbol));
  auto create = reinterpret_cast<rex::system::GpuCreateFn>(
      GetProcAddress(plugin, rex::system::kGpuCreateSymbol));
  if (!version || !create || version() != rex::system::kGpuPluginAbiVersion) return 12;
  rex::system::GpuCreateInfo info{sizeof(rex::system::GpuCreateInfo), "any"};
  std::unique_ptr<rex::system::IGraphicsSystem> graphics(
      create(rex::system::kGpuPluginAbiVersion, &info));
  if (!graphics) return 13;
  std::puts("PRESENTER_PLUGIN abi=1 backend=any");
  if (!session.Initialize(graphics.get())) {
    session.Shutdown();
    graphics->Shutdown();
    return 14;
  }
  std::thread bounded_stop([&session, duration] {
    std::this_thread::sleep_for(std::chrono::milliseconds(duration));
    session.RequestStop();
  });
  const int loop_status = session.Pump();
  bounded_stop.join();
  session.Shutdown();
  graphics->Shutdown();
  graphics.reset();
  std::printf("PRESENTER_SHUTDOWN clean=%u loop_status=%d\n",
              unsigned(session.clean_shutdown()), loop_status);
  return session.clean_shutdown() && loop_status == 0 ? 0 : 15;
}
