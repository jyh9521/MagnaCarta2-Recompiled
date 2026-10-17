# 阶段 5：真实标题入口与首个阻塞

## 结论与边界

**Verified**：固定 disc-1 XEX 通过 SDK 正式 `LoadXexImage` 装载后，全部 197 个生成对象链接的宿主创建真实主线程，执行原入口 `82868EC0`（生成名 `xstart`），进入 `82E1F578` 主流程。探针没有调用替代入口、手工调用 native 初始化器、写入 vtable、写入 GNatives，或修改游戏/SDK。

正式 kernel、SDL audio、input 与无呈现 GPU 初始化后，首个稳定可重现的兼容阻塞是：

```text
[FATAL] Call to invalid or unregistered function at guest address 0x8234FF10
TITLE_FATAL_PPC ... lr=823B9B1C ctr=8234FF10
exit_status=3221226505 (0xC0000409)
```

`823B9B18 bctrl` 从对象偏移 `0x11C` 读取构造回调并间接调用。目标 `8234FF10..8234FF40` 是原始代码中的独立 `0x30` 字节 leaf；本轮固定生成映射没有它，邻近 PDATA 也不覆盖它。`82D6C834` 的 `lis/addi` 组合构造该地址并将其传给 `823A6150`。这不是可通过假返回值修复的缺失导入；下一阶段应增加有证据的代码入口提示并严格重新生成、编译和验证。

**High-confidence deduction**：该目标缺失源于间接构造回调未被当前代码发现覆盖。当前证据不证明其他间接回调均完整，也不证明补齐它之后即可完整启动。

本轮没有执行该缺失函数，没有绕过 SDK fatal，没有显示游戏首帧，没有验证完整游戏启动/退出或可玩性。`diagnostic_success` 只表示阻塞证据成立，`game_boot_success` 和 `shutdown_verified` 都是 `false`。

## 实际初始化合同

宿主采用随固定 SDK 提供的 `share/rexglue/rex_app.cpp` 的真实配置合同：

- `config.kernel_init = rex::kernel::InitializeKernel`；
- `REX_AUDIO_BACKEND(rex::audio::sdl::SDLAudioSystem)`；
- `REX_INPUT_BACKEND(rex::input::CreateDefaultInputSystem)`；
- `tool_mode=false`，无窗口、无呈现，真实 Xenos 图形系统。

SDK 便利包装器 `LoadGpuPlugin("xenos")` 在隔离实验中出现 `0xC0000409`。宿主转而使用 **同一 SDK 公开的插件 C ABI**（`rex/system/gpu_plugin.h`）：`LoadLibraryW`、`rex_gpu_abi_version`、`rex_gpu_create`、严格 ABI 版本/结构大小检查，得到真实 `IGraphicsSystem`。DLL 保持进程生命期，不替代 GPU 实现，不修改包装器/SDK。复制的 SDK DLL 与实际加载路径、原文件 SHA-256 全部核验；便利包装器失败记录保留。

`PrepareModuleLaunch` 创建 suspended 主线程后，`Resume` 启动真实生成代码。`TITLE_RESUMED` 本身仅证明主线程恢复成功；随后抓到包含 `xstart` 的真实调用栈才作为原入口已经执行的证据。

## 保留的失败及修正

以下目录均位于忽略的 `local/analysis/phase5/`，不得提交其中的原始游戏数据、生成代码、对象或二进制。

| 实验目录 | 原始结果与处理 |
|---|---|
| `boot-first` | C++ 编译失败：误用受保护的 `GetWaitHandle` 与 `PPCRegister` 转换；使用公开 thread handle 与 `.u32` 后修正。Python 模块路径/链接器路径错误另保留在 console 日志。 |
| `boot-second` / `boot-export-audit` | 真入口 AV，读取 guest `0x10193`；发现 kernel callback 缺失而非游戏资源问题。 |
| `boot-kernel-init` | 正式 kernel callback 修复变量导入：`82000708 -> 30006000`、`82000710 -> 30002000`。随后 SDK 音频系统缺失导致 host 空指针；按正式音频 factory 修复。 |
| `boot-backends` | 便利 GPU loader 出现 `0xC0000409`；隔离并保留，不归咎游戏字节。 |
| `boot-audio-input` | 已进入 main，缺 `MC2Game/Xbox360TOC.txt` 后 AV；通过只读、有哈希的原盘成员 staging 修复。 |
| `boot-staged-toc` | 缺 `Config/Xenon/Cooked/Coalesced.ini`；继续 staging 原件，不修改内容。 |
| `boot-staged-coalesced` | 20 秒观察窗口结束，线程仍 running；这一次超时本身不作为定位。 |
| `boot-sampled-coalesced` / `boot-ring-measurement` | 三次 native/PPC 采样表明真实 GPU ring 等待；read 指针 `FFC9B000` 固定 `0`，write 为 `15`。补齐正式 GPU 后该等待解除。 |
| `boot-c-abi-gpu` | 真实 GPU 创建 render target / pipeline；继续后缺 `Localization/Coalesced.int`，有界 staging 修复。headless `IssueSwap: presenter is null` 被记录，不等于可见帧。 |
| `boot-localization` | 6 个已校验选定成员（运行命中 int，jpn/kor 为候选）存在后首次触发未登记目标 `8234FF10`，`0xC0000409`。 |
| `boot-fatal-diagnostic` / `boot-final` | 只读日志 sink 补充真实调用栈和 PPC 寄存器，保留原 SDK fatal 终止；阻塞重复出现。 |
| `boot-final-guarded` / `boot-independent` | 将 runtime assets 守卫纳入诊断判定后全新重编译/链接、独立重跑；同一 `8234FF10` fatal，输入与资源不变。 |

原盘成员提取见 [运行时数据 staging](RUNTIME_DATA_STAGING.md)。每个实验使用独立目录，验证 source XEX、实际 VFS root 中同名 XEX、整个 staged root、SDK、生成树及 197 个对象的输入身份，运行前后哈希不变。`UPDATE:\` 未挂载、`XFileXctdCompressionInformation` 未实现等日志保留，但没有将其自动认定为最终阻塞原因。

## 调用路径与 native 初始化效果

日志 sink 属于官方 `LogConfig.extra_sinks` 观察扩展。它只在 SDK 报告未登记目标时采集 `CaptureStackBackTrace`、当前 PPC 寄存器及只读 GNatives；原 fatal 仍执行并终止进程。普通 AV 由只返回 `EXCEPTION_CONTINUE_SEARCH` 的 VEH 记录。采样窗口结束时通过短暂 `SuspendThread` / `GetThreadContext` / `RtlVirtualUnwind` 观察栈，之后恢复线程并终止隔离进程，不修改 guest 字节或寄存器。

最终 fatal 的真实 host 栈按 linker map 的 RVA 解析，调用方向为：

```text
xstart -> 82E1F578 -> 82E1F528 -> 82E21740 -> 82E203C8
 -> 82E38270 -> 82D6CCA0 -> 823A4CA0 -> 823A4BB0
 -> 823B99C0 -> SDK invalid/unregistered-function fatal
```

RVA 解析使用最近前置函数符号，不等同于源行定位；直接间接调用位置另由实际 `lr=823B9B1C` 与原生成 `823B9B18 bctrl` 相互核验。

真实标题初始化链产生 `guard=1`、4096 个非零 GNatives slot、3794 个 fallback、`[29]=82508E60`、`[146]=8250BAF0`。本轮没有手调前阶段的两个注册器；该观测与前阶段夹具实验有本质区别。注册效果不自动证明全部 3873 个静态初始化目标都已执行；完整初始化表分析见 [启动链研究](RESEARCH_STARTUP_CHAIN.md)。

## 复现

先完成 197 对象编译以及原盘成员 staging，再在仓库根运行（替换为当前机器的实际 VS 路径）：

```powershell
python -m tools.research.probe_title_entry `
  --build-dir local/analysis/phase3/module-modified `
  --generated local/analysis/phase3/branches-bounded/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --xex local/analysis/phase2/default-disc1.xex `
  --game-root local/analysis/phase5/game-root-05 `
  --gpu --output local/analysis/phase5/boot-final
```

输出目录必须不存在。工具返回 `0` 意味着观测到有栈和 SDK 日志佐证的阻塞，**不是游戏成功运行**。宿主真实退出码在 `run.json`；编译、链接、运行命令与哈希在 `host-link.json`、`inputs.json`。`title-entry.json` 分开记录原入口执行、main、故障、内部观察窗口、进程 timeout、游戏数据输入身份及游戏成功状态。

便携单元测试只验证报告/哈希守卫合同，不取代 Windows 上真实运行：

```text
python -m unittest discover -s tests -p test_title_entry.py -v
python -m unittest discover -s tests -p test_link_module.py -v
```

后续代理提示可复用：

```text
从已验证的 phase5 boot-final 未登记回调 8234FF10 继续；保持原 XEX、SDK、197 对象和六个 staged 成员的哈希守卫。先验证该 0x30-byte leaf 与 823B9B18 间接调用关系，再建立代码发现配置实验。保留旧生成树和 fatal 基线，不用空 stub、不跳过断言、不手写 vtable/GNatives。严格重新生成和全量编译后复测原入口，分别报告构建、执行和可见帧证据。
```
