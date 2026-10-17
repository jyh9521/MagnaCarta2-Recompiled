# 有界 SDK presenter 宿主实验

## Verified：公共契约与独立实验

本轮新增 `src/host/presentation_probe.h`、`src/host/presenter_probe.cpp`、
`tools/research/probe_presenter.py`、`tests/test_presenter.py`。未复制 SDK 实现、修改 SDK、
加载 XEX、生成模块或游戏资产，也未调用 `SetupGuestGpu`。

ReXGlue v0.10.0 本地固定 SDK 的公共契约：

* `include/rex/ui/windowed_app_context_sdl.h`：先 `Initialize()`，以
  `RunMainMessageLoop()` 执行阻塞式 UI 循环；`ProcessEvent` 是私有实现，不另造事件泵。
* `include/rex/system/interfaces/graphics.h:34..50`：有显示需求时
  `SetupPresentation(context)` 必须先于 `SetupGuestGpu`。无显示 provider 不能原地升级。
* `include/rex/ui/window.h:155..206,289..291,354`：
  `Window::Create` → `Open` → `SetPresenter`；Windows 原生句柄为 HWND。
* `share/rexglue/rex_app.cpp:308..376` 的官方应用也采用上述次序；
  `575..606` 先拆 presenter/window，再销毁 runtime。
* `include/rex/cvar.h:122..125,192` 提供 `Init(argc,argv)`、
  `ApplyEnvironment()`、返回 bool 的 `SetFlagByName(name,value)`。
  独立实验传入 `--headless=false`；标题实验应只在显式 presenter 模式覆盖该选项，
  不应改变原 headless 基线。

源文件 SHA/行见证另存 `local/analysis/phase10/next-presenter-contract.json`。
插件 DLL 固定 SHA256
`0c23cfa23fc4fa5638dc8a3dc0de87b1041d97705d4677774083f1f350cd8d89`，
runtime DLL 固定 SHA256
`e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a`；
工具在编译前拒绝不匹配版本，并比较源码、库、头树在执行前后的身份。

## Session 生命周期边界

`mc2::host::PresentationSession` 的公共接口是 `Initialize(IGraphicsSystem*)`、
`context()`、`window()`、阻塞 `Pump()`、跨线程 `RequestStop()` 和 UI 线程 `Shutdown()`。
session 不拥有 graphics/runtime；context 必须比后者活得久。
`RequestStop()` 仅排队 `RequestDeferredQuit()`，不拆 GPU/window。
窗口关闭请求也只退出循环并否决立即关闭；调用者先停止活跃 guest/GPU，再调用 `Shutdown()`。
独立实验没有 guest，可以正常 detach、close、销毁 HWND、shutdown graphics。
标题仍活跃时的有界进程终止不等同这条正常清理路径。

SDK 没有此次可用的公共隐藏创建选项：辅助进程按 hidden 启动，`Open` 后立即用公开
HWND 执行 `ShowWindow(SW_HIDE)` 并验证 `IsWindowVisible==false`。
这不保证 `Open` 前完全没有瞬时窗口。未绕过 protected/private 成员。

## 实测命令、结果与失败保留

```powershell
python -m unittest discover -s tests -p test_presenter.py -v
python -m tools.research.probe_presenter --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --output local/analysis/phase11/presenter-final --duration-ms 500
```

11 个便携单元测试通过；独立编译/链接 exit=0、运行 exit=0（1.163s，包括 500ms 循环），
CLI 输出 `PRESENTER standalone=1 success=True`，输入身份比较全部不变。
本机 GPU 日志确认 SDL windows 驱动、RTX 4070 Laptop GPU、D3D12 device 创建。
`presenter-final/run.txt` 的完整生命周期为：

```text
PRESENTER_SCOPE xex_loaded=0 guest_gpu_setup=0 game_assets=0
PRESENTER_PLUGIN abi=1 backend=any
PRESENTATION_CONTEXT initialized=1 ui_thread=1
PRESENTATION_SETUP status=00000000 has_presentation=1 presenter=1
PRESENTATION_WINDOW open=1 hidden=1 binding_requested=1
PRESENTATION_LOOP enter=1
PRESENTATION_LOOP exit=0
PRESENTATION_WINDOW_CLOSED closed=1 native_destroyed=1
PRESENTER_SHUTDOWN clean=1 loop_status=0
```

可执行文件 SHA256 `405d0767215617bee2f74e222ba0718b8a7b0aa3b83fa7e257c0f78d6fb03ce4`；
运行日志 SHA256 `9a1eebf187ced05a979212ef186944c322ae78938bedc5b598763ffb55cda256`。
工具保存精确编译/运行 argv、退出状态、时间、文件 SHA 和失败日志。

失败保留：`presenter-first` 和 `presenter-second` 的编译 exit=1，原因是误用
protected `Window::presenter()`/`HasSurface()`；修正为只用公共调用，绝不放宽访问权限。
一次 PowerShell 内嵌 Python 引号错误未修改源码，随后以补丁工具修正。
`python -m unittest tests.test_presenter` 因 tests 不是 package 而失败；改用上列 discover 命令，
不是跳过测试。`presenter-third` 是首次成功，`presenter-final` 是最后源码的独立新目录重跑。

## DLL 身份拒绝守卫的补充复验

最终工具通过独立 `verify_sdk_identity` 在创建输出目录、读取后续构建输入和编译之前，
验证上述两个完整支持 SHA；不是仅将任意本机 DLL 的身份写入报告。
新增支持身份正例、错误 plugin 和错误 runtime 两个 CLI 负例，后两者均断言构建未调用、
输出目录不存在。共 **14 个测试通过**；负例不修改进程全局 `os.name`，保持便携测试路径语义。
再次以相同命令将 `--output` 分别指定为新的 `presenter-guarded`、
`presenter-guarded-final`，均编译 exit=0、运行 exit=0、CLI success=True，输入身份不变；
原 `presenter-final` 证据完整保留。最终源码见证以 `presenter-guarded-final/presenter-verification.json` 为准。

## 证明上限与标题集成

Verified：真实非空 SDK presenter、有效隐藏 HWND、公开 `SetPresenter` 已调用、
官方 UI 循环运行和正常清理。`binding_requested=1` 不等同于受保护 getter 的读取结果。
本轮没有公开 surface getter，日志亦没有 swapchain/呈现成功的正见证，故
**surface_verified=false、first_frame_verified=false**。不推断此前标题 wait 由 presenter 缺失造成。
根代理已完成同一 session 的真实标题有界集成实验；实际 swap、等待对象与线程现场，
以根代理汇总的 `docs/PHASE11_RESULTS.md` 为准。独立宿主成功不是游戏显示验收，
本文件不根据标题集成状态补填缺少的 surface/首帧证明。
