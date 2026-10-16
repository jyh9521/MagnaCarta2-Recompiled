# 完整生成模块的宿主链接与 SDK 初始化实验

## Verified：从全部对象到可执行宿主

阶段 3 的 197 个成功 COFF 对象作为**全部显式输入**传入 VS 2022 x64
`link.exe`，没有建立只抽取少数函数的静态库，没有补空 stub，也没有用 `/FORCE` 忽略未解析符号。
链接使用 `/OPT:NOREF /OPT:NOICF /INCREMENTAL:NO /Brepro`，保留全部对象和独立符号；
公开仓库仅保存自写入口和工具，不保存商业游戏衍生源码、对象、链接 map 或可执行文件。

- `tools/research/link_module.py`：验证成功构建记录、全部 197 个对象的 SHA/大小、
  生成目录、SDK include 与 Clang resource include，再链接、执行、复验输入不变。
- `src/host/module_probe.cpp`：调用官方 SDK 的 `rex::Runtime::Setup(PPCImageConfig, config)`，
  `config.tool_mode=true`。没有调用 `LoadXexImage`、`LaunchModule` 或任何游戏 entrypoint。
- 真实依赖为 SDK v0.10.0 的 `rexruntime.lib`、`spdlog.lib`、`fmt.lib`，以及 Windows
  `dxgi.lib`、`dxguid.lib`。运行时 DLL 通过 `GetModuleHandleA/GetModuleFileNameA` 实测，
  必须等于输入 SDK 的 `bin/rexruntime.dll`，不把另一路径的 DLL 当作验收对象。
- LLVM 20.1.8 编译器 SHA 固定为阶段 3 同值；MSVC linker 文件 SHA、系统 INCLUDE/LIB
  和版本随记录保存。系统库/系统头尚未逐文件固定，不承诺跨主机 EXE 字节一致。
- 完整 SDK 树前后逐文件哈希；源文件另拷贝为输出目录的 `source-0.cpp`/`source-1.cpp`，
  同时保存原路径和快照 SHA。输出目录必须新建，所有尝试日志不覆盖。

## 可复现命令

在项目根目录执行，原版输入、固定 SDK/LLVM、阶段 3 对象先按前述文档准备：

```powershell
python -m tools.research.link_module --build-dir local/analysis/phase3/module-modified --generated local/analysis/phase3/branches-bounded/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --output local/analysis/phase4/host-validated
```

本次输出 `HOST_LINK objects=197 mappings=58408 inputs_unchanged=True success=True`，exit=0。
独立编译入口、真实链接、真实运行各 exit=0。`host-link.json` 保存每一步真实 argv、
工作目录、标准输入 DEVNULL、日志 SHA、退出码和 EXE/map 身份；`inputs.json` 保存输入身份。
逐 TU 已有对象在链接前后 SHA/大小相同，没有重编旧对象冒充本次链接成果。

运行实际输出包含：

```text
SETUP status=00000000
REGISTRATION count=58408 base=mapped
MEMORY roundtrip=12345678
SHUTDOWN complete
```

`mc2_probe_RegisterFunctions` 对 SDK `FunctionDispatcher` 真实登记。
入口逐个遍历 `PPCFuncMappings`，对 58,408 个地址检查 `GetFunction(address)==原host指针`，
任一失败立即非零退出。随后通过 SDK `SystemHeapAlloc` 分配 guest 内存，写/读四个字节、
核对后 `SystemHeapFree`。`Runtime::Shutdown` 实际返回并由进程正常退出。
这验证了映射、函数表、kernel state 和受控内存往返，不证明标题数据装载或 UE3 全局状态已初始化。

链接 map 实际包含全部 197 对象。58,408 个注册项中包含 58,162 个生成函数和 246 个导入项；
全部导入符号的链接解析不等于全部导入功能的运行语义已经测试。

## 可选真实 native 调用入口

加 `--probe-source src/host/native_add_probe.cpp` 后，入口真实调用
`RunNativeAddProbe(Runtime&)`，再要求 `NATIVE_PROBE status=0` 才验收。
**执行前**必须匹配已验证生成树 SHA：
`2f665e02be216bc4e87ed8544bd29bf2d0b24dde92857506b492bd18056a43db`。
这防止固定 guest 地址探针误用于另一套 197-TU 游戏版本。
JSON 保存 native profile 和附加源码 SHA；不是通过固定对象数量推断版本相同。

```powershell
python -m tools.research.link_module --build-dir local/analysis/phase3/module-modified --generated local/analysis/phase3/branches-bounded/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --probe-source src/host/native_add_probe.cpp --output local/analysis/phase4/host-native-initialized
```

真实调用细节、名称注册证据、8 组输入输出和合成内存边界见 native 实验文档。
最终探针不再手写 GNatives slot：它复现两个经原始镜像核对的静态 vtable 指针，
实际执行 `82E707C8`、`82E73108` 原注册函数及第一次注册的重复路径，由原机器代码填写 GNatives。
实测 guard=1、4,094 个默认 fallback 槽、重复注册 index=29、两项真实绑定均正确，随后 8 组 Add 调用通过。
这些 guest frame/字节码和两个静态指针仍是明确的受控 fixture；没有运行完整游戏启动注册链，
没有以两项 vtable 数据复现充当全游戏 UE3 初始化，也没有把结果提升为可游玩或首帧验收。

## 保留的失败与中间态

`local/analysis/phase4/host-failures.json` 索引以下实际尝试，未覆盖日志：

1. `host-first/command.json`、`link.txt`：Clang 一次传入主 CPP 与 197 对象时还指定 `/Fo`，
   实际 exit=1，报不能为多输入指定单个 `/Fo`；未生成宿主 EXE。改为先单独编译入口、再显式链接。
2. `host-second/compile.txt`、`link.txt`：入口编译/完整链接已经 exit=0；Python 驱动随后
   用区分大小写的 `env['PATH']` 访问实际 `Path`，KeyError，驱动 exit=1。
   修正为大小写无关的 PATH 键查找；同目录后续运行的 exit=0 不抹掉最初驱动错误。
3. `host-final` 是首次成功宿主，但后续入口加入 DLL 身份和可选 native marker，原输入源已漂移。
   该目录仅保留历史成功，不作为最终源码冻结证明。`host-validated` 才是最终冻结入口的重新完整链接。
4. `host-native-first`、`host-native-final`、`host-native-validated` 保留集成过程；
   增加支持游戏 profile 守卫后目录为 `host-native-profiled`。它仍直接填两个 GNatives 槽，
   后续原注册函数探针继续推进；最终实际执行原 initializer 的目录为 `host-native-initialized`，
   该目录重新链接全部 197 对象，没有复用旧宿主 EXE。

不存在链接失败后删对象、重定向未知符号到空函数或加载另一版本 DLL 的“修复”。

## 自动测试与后续缺口

`python -m unittest discover -s tests -p test_link_module.py -v`：16 tests / OK。
公开测试只使用自制文件和模拟进程，覆盖完整 197 对象保留、坏对象/缺项/重复/越界路径、
生成源变化、源集合不匹配、失败/超时/启动错误日志、日志不覆盖、PATH 大小写、
已知 native profile 通过和未知 profile 拒绝；与真实 SDK 链接验收分开计数。

下一步仍需真实 XEX 镜像装载、导入初始化语义、线程/PCR、UE3 对象与 native 注册生命周期、
图形/音频/输入以及游戏 entrypoint 启动验证。工具模式初始化和一个受控真实调用不构成这些验收。
