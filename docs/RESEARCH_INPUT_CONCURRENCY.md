# 输入并发：同对象故障捕获与未决写入来源

> 2026-10-18：Windows x64 原生重编译研发无限期暂停。本页原生路线步骤与待办仅作历史复现记录，不作为近期交付任务；现行方向为原版 Xbox 360 资源汉化和 Xenia 验证。参见[技术归档](NATIVE_RECOMPILATION_ARCHIVE_2026-10-18.md)。

## 固定基线与源码状态

2026-10-18本轮只研究SDK输入并发，不部署资源、不开始翻译。`phase37/entry-snapshot`保存进入任务时314份源码文件、完整hash、Git暂存/工作区差异；已有修改按字节保留。当前源码具有共享门锁实现，属于MODIFIED，不是未安装实现的BASELINE。默认运行开关仍为关闭；实现状态、每进程installed状态与历史源码回退分别判断。

固定输入位于ignored `local/analysis/phase37/fixed-inputs.json`。目录hash采用既有`inventory`的相对路径→SHA256字典排序JSON计算，不能与单文件hash混用。

| 输入 | SHA256 |
|---|---|
| 当前游戏EXE | `323ad3852a94a2decfef5e5d86e5bf4b03020230b07884d5c2c80a3e0d7e939c` |
| 原始Disc1 XEX | `26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f` |
| SDK完整目录 | `2e090f7a2a879859159a47ace73b200e96ecbe103358b560aba364ca04d3b9fc` |
| rexruntime.dll | `e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a` |
| strict生成树 | `72a58849cd4872c8457b16fe36da86a1026327b764c40d1fdfa405895cbaacff` |
| 原197对象构建目录 | `4cdd37825da27a40da5248c578845c8f67befa23074460b889580aab266035e4` |
| phase35/root-structures资源根 | `227b10db9c9022fc87d4a7a9dfff2d5a6c5906ae1eed90bf2663b34dea555052` |
| 上轮SDK探针EXE | `6858e4eedd73d13153bb4258a5232d8589d0be8ff5ae49d29e6d150e3671eb87` |

固定目录、原SDK、原XEX、游戏EXE、生成体均未修改。已有[共享门锁与回退](RESEARCH_INPUT_SERIALIZATION.md)继续作为实验控制；本轮没有新增生产修复，也没有把无锁失败改成成功。

## 诊断实现与采集边界

原SDK探针先原样执行，确认失败后才增加独立诊断。`input_probe_trace.h`每worker预分配65536个48字节记录，两线程分区追加；全局Interlocked序号只标定观测事件顺序。每条包含InputSystem地址、线程ID、API、迭代、门锁状态、深度和回调参数地址。字段完成后提交count；离线报告只在进程结束后读取已提交项，不读取运行中的SDK容器，不根据非原子快照猜测写入者。饱和计数、未返回调用及失配均显式保留。

记录点为请求、进入原SDK、EnumerateDevices进入/退出、原SDK返回、wrapper返回、join后的Shutdown进入/退出。枚举参数是RefreshDevices的**线程局部enumerated vector**，不是共享devices_；记录不把driver的push_back冒充共享容器写入。开启记录会扰动时序；未开启记录的原探针作为独立控制。

`input_probe_capture.cpp`作为外部Windows debug-event父进程，记录first/second chance异常、所有线程CONTEXT、至多32层栈及原生退出码；有界60秒，timeout标记不是AV。采集不插断点、不改SDK指令、不改线程寄存器、不吞异常。仅系统初始调试断点由调试器继续，其余异常按NOT_HANDLED继续。模块基址、大小与原PE异常目录来自暂停进程的ReadProcessMemory，StackWalk64使用这些真实RUNTIME_FUNCTION表，避免依赖私有PDB或网络符号。minidump单独记录成功/失败，父程序exit0仅表示采集程序完成，子程序native退出另列。

旧诊断版本的符号初始化失败、仅单帧输出及错误ADDRESS64初始化记录全部保留，不作为有效调用栈。最终版本与v5的有效栈使用显式AddrModeFlat和真实PE unwind表。一次离线汇总早于矩阵结束的草稿标为`preview-unaccepted`，重新等全部八组结束后采集的`events-final.json`才作为结论依据。

## 负八AV证据链（Verified）

最终`trace-final-cross/CAPTURE_ROLLBACK_OFF`中：

- 两线程对应同一InputSystem `0x87CB8EFDC8`；线程27504为GetState第9轮，线程3740为SetState第8轮，两者gated=0、depth=1。
- 全局序号102和107分别记录两个原SDK进入；109、110是各自枚举退出。两次delegate均未返回；110个事件无丢失，同对象调用峰值2。
- 线程27504直接采样`RIP=rexruntime+117F11, RCX=0, RDI=0x26683E59F88`，异常读取地址`FFFFFFFFFFFFFFF8`；线程3740也在该指令捕获RCX=0及相同RDI。
- 各自的同线程栈为`117F11 → 115130 → 1156F0/GetState`、`117F11 → 115130 → 1158E6/SetState`。原指令仍为`mov r8,[rcx-8]`，不是根据日志相邻行配对。second chance后native `3221225477/C0000005`；minidump成功。

此样本首次直接复现与历史负八地址、固定DLL、故障指令一致的症状，并把同对象、API入口、线程、寄存器和边界顺序关联。它仍不是历史A2/B3原对象的身份或原始破坏写入历史；**未捕获SDK内部哪条写指令最先损坏字符串元数据**。

## 堆终止证据链（Verified，独立记账）

最终`heap-capture/4`中InputSystem为`0x4FD2AEFCA8`。线程46440在SetState第4轮序号101进入后未返回；线程48876在GetState第18轮序号138进入，140完成枚举，两个调用共享对象、gated=0、peak2、140事件无丢失。

线程46440在NTDLL捕获first/second chance `C0000374`；同线程展开栈经NTDLL堆路径、ucrt `+12D7B`、SDK `117F31 → 115130 → 1158E6`，即SetState刷新清理中的释放调用。native `3221226356`，minidump成功。此前独立捕获的AV与该样本不合并，检测到坏堆的线程也不自动等于首次破坏堆的线程。

上轮原探针首个无锁控制也退出C0000374，但没有本轮debug事件栈；早期游戏堆终止与当前独立样本不能只凭同码建立同根因。旧捕获中minidump失败的记录仍保持失败。

## 生命周期、锁顺序与覆盖范围

独立探针的Setup、AddDriver、SetDeviceAssignment在worker启动前完成，两个join完成后才Shutdown及解除trace映射；失败样本均未到Shutdown记录。该复现不需要并发销毁对象，且driver无共享可变状态。每线程深度1、无回调重入；这不是任意驱动/SDK生命周期路径的全局证明。

既有host的门锁只覆盖EXE的GetCapabilities/GetState/SetState导入及存在时的GetKeystroke。合成driver快照mutex位于调用门锁内部，已读代码没有持driver锁反向进入门锁的路径；同线程递归由recursive_mutex允许，但SDK容器能否承受任意回调重入仍未验证。异常传播/RAII解锁、PPCContext全字节、64位寄存器、guest内存、errno/GetLastError及真实只读IAT交换/恢复沿用并重跑原生fixture，不重建返回值。

源码审查未证实当前host存在绕过门锁的新增输入调用者，因此不扩大IAT范围。SDK其他模块的直接调用、驱动增删、Shutdown、assignment或窗口切换不由host IAT门锁覆盖；这些是覆盖边界，不是已证实的本轮故障源。未对发行SDK实施全局修复。

## 同输入交叉与压力测试

每组输入相同：无XEX、同一SDK、GetState/SetState各10000次，name/guid各8192字节。单个矩阵内保持同一探针EXE，不跨版本混合比较。

| 矩阵 | 原始OFF | ON | 实际关闭回退OFF | 再开ON |
|---|---|---|---|---|
| 原上轮探针 | C0000374 | 完成/0 | C0000409 | 完成/0 |
| 最终trace探针，不附调试器 | C0000374 | 完成/0 | HOST_TIMEOUT/124 | 完成/0 |
| 最终trace探针，外部捕获 | C0000005/117F11 | 完成/native0 | C0000005/117F11、负八读取 | 完成/native0 |

最终四个ON样本各读写10000、errors0；每份120002事件、peak1、dropped0、无未返回调用、Shutdown结束。两线程真实SDK压力与既有8线程8000次门锁fixture分别记账。额外最多六次有界无锁捕获实际执行五次：AV、AV、C000001D、AV、C0000374；没有丢弃不同症状。C000001D位于原clear `+117F93`的`ud2`，不归类为AV。timeout未取得挂起栈，不命名为死锁。

固定游戏EXE保留原START/A确认、SDK和资源，同进程配置依次OFF/ON/OFF/ON，各新建进程：首轮OFF native `3221225501/C000001D`，SDK `117F93`，GetState及SetState刷新栈；后三组native26、45秒观察边界，SDK图像读回有效。OFF回退wrapper计数为0，ON安装成功、peak1。未重现的OFF样本不抹掉首轮失败，exit26不算正常退出，图像也不证明首场景/移动/战斗。旧EXE未重建，既有启动路径没有新增补丁；有限回归窗口未观察到新增门锁故障，不能宣布无回归或游戏可玩。

## 可复现入口与证据

先使用既有固定Windows工具链；`build_input_probe`验证SDK DLL/Clang身份、快照四个诊断源文件，编译两个独立程序并记录完整命令、原文输出和hash。该工具不生成游戏对象，不加载XEX，不修改SDK；已有输出目录拒绝覆盖。

```powershell
python -m tools.research.build_input_probe --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --output local/analysis/input-concurrency-repro
$env:PATH = "$(Resolve-Path local/upstream/rexglue/sdk/win-amd64/bin);$env:PATH"
$env:MC2_INPUT_PROBE_TRACE = "$PWD/local/analysis/input-concurrency-repro/events.bin"
# capture输出native退出码；父程序返回0不代表被测程序成功。
& local/analysis/input-concurrency-repro/capture.exe "$PWD/local/analysis/input-concurrency-repro/probe.exe" concurrent "$PWD/local/analysis/input-concurrency-repro/fault"
# 进程完全结束后才读取；下次实验更换trace路径，CREATE_NEW禁止覆盖。
python -m tools.research.input_probe_trace_report local/analysis/input-concurrency-repro/events.bin --output local/analysis/input-concurrency-repro/events.json
```

同输入交叉使用`probe.exe concurrent 10000 8192`与`probe.exe serialized 10000 8192`，父进程设60秒界限。完整`run.json/run.txt`、输入环境、8组最终矩阵、5组追加故障、minidump、前后输入身份、准备失败及源码事务保留于ignored `local/analysis/phase37/`。首次builder裸link.exe路径查找失败exit127已保留，修正为vcvars环境中解析的绝对linker路径后在新目录重建成功。首次unittest模块名调用因tests不是package失败，改用discover后复跑；不覆盖失败记录。

## 结论与唯一后续任务

已证实同一个真实SDK InputSystem的未加门锁输入调用能够重叠并发生刷新清理AV/堆终止；共享门锁控制在有限样本完成。已增加的只有可复现采集、严格离线验证与构建工具；生产门锁和默认关闭语义不变。首个破坏共享字符串/容器元数据的指令、历史游戏负八与堆终止的写入来源、SDK其他调用者与重入生命周期仍未修复。

下一轮唯一优先任务：在固定SDK/同对象复现中捕获共享devices_字符串元数据的**首次破坏写入指令及写入线程**，再判断是否存在host门锁未覆盖的调用者；继续不推进资源部署或翻译。

## 本轮验证与实际回退

本机完整测试为1239项、skip3、exit0；其中配置最终真实SDK探针，执行了原生门锁/ABI夹具和trace的独占文件拒绝覆盖检查。目录隔离事务的BASELINE为1234项/skip30，MODIFIED为1239项/skip31，真实脚本回退后为1234项/skip30，三组均exit0；隔离目录没有本地SDK，因此跳过数不与本机实际运行混用。事务literal输出为`ROLLBACK restored=4 removed=6 original_hashes=restored`，314个进入任务时的源文件hash均恢复，新增6文件实际移除；主工作区和MODIFIED_FILE.cpp保留诊断修改态。已有生产门锁的ABI、客体内存/寄存器及error-state透传fixture再次通过。

本机证据四产物位于`local/analysis/phase37/source-transaction/`：MODIFIED_FILE.cpp、DIFF_FILE.patch、VERIFICATION.txt、可执行ROLLBACK.sh。报告包含baseline/modified/restored全量测试原文、命令、输入、exit与真实脚本回退结果；SDK模式回退OFF重新出现失败与源码hash回退分别记录。测试结束后的文档收尾与Git/CI状态单独记账，不改变这些诊断源和固定游戏输入的身份。

本轮retention保留所有phase37原始失败trace、日志、dump与构建身份，以及全部活动构建输入。仅退休2份完整hash一致的可重建输出，净删除291958字节；包含恢复测试后再次退休的累计删除为491638字节，不等同净节省。另清除416份可再生Python字节码、6578480字节。静态运行库门锁fixture经过真实删除、恢复hash核验及再次运行，exit0、ABI偏移和actual_restore=1均保持；两张原ISO完整hash、固定7项输入及兼容junction验证保留。原始故障记录未删除。
