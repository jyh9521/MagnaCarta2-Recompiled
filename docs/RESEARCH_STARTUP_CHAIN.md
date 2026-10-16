# 原始 XEX 标题入口与 CRT 初始化链

## Verified：静态恢复边界

本节由 `tools/research/analyze_startup.py` 只读核验，不执行 PPC 或构造函数。
工具复用已有的原 XEX SHA-256 守卫和 pinned Xenia loader source 守卫，解密/展开仅供内存分析；
不输出 key、不修改原 XEX。工具进一步固定四段原始指令的完整 SHA-256，并核对生成注册见证文件。
全量输入 hash 在分析后重新检查，结果保存在本地 JSON。
CLI 同样固定 `mc2_probe_init.cpp` 与 `mc2_probe_recomp.15.cpp` 的完整文件 SHA-256，
两值分别为 `8fbf9073bfcff48476df7335f7f296c89ab092d4b8af9b85cfdf348de377ac1a` 和
`9c08b277fa287917337d5a1c9e65d7d363e8675f6d6568c76279ffe24eb896af`，
均与阶段 3 实际全量编译 `module-modified/inputs.json` 的生成文件清单及磁盘文件一致。

PE32 `AddressOfEntryPoint=00868EC0` 加 image base `82000000`，与 XEX `entry_point=82868EC0` 一致。
TLS 可选头具有 64 slots，但原始数据地址、原始数据大小和总数据大小均为 0；默认栈大小为 `00040000`。

`PPCFuncMappings` 将 `82868EC0` 映射为 **xstart**。该符号是 `mc2_probe_recomp.15.cpp`
中的真实 `DEFINE_REX_FUNC(xstart)` 生成函数，不是 SDK 替代入口。工具要求唯一真实函数体，
并将其中全部直接 `bl` 的目标/顺序与原入口的 440-byte PPC 范围逐项核对。
helper 只证明词法调用序列一致，不把条件路径等同于已经执行的路径；
CLI 完整文件哈希守卫另行拒绝只伪造匹配注释、映射或函数壳的输入。

初次检索只查 `sub_82868EC0` 名称，曾误判入口被 SDK 替代。
反证为真实生成 `xstart` 函数体及宿主 linker map；本地旧 JSON 保留在
`local/analysis/phase5/startup-entry-misclassification.json`，最终结果明确 `original_entry_body_generated=true`。
新增测试防止仅凭 mapping 名称再次推导替代入口。

## Verified：调用顺序与真实初始化表

原入口在寄存器保存后依次包含以下调用；条件终止分支和具体路径应由实际执行验证：

1. `8286A1A0`，内部首先调用 `8286A0D0`。
2. `82869FF8`，入口设置 `r3=1`，遍历临界区保护的回调链。
3. `82868CD8`，随后存在条件终止调用。
4. `8286FBA0`，包含 TLS 分配/设置、堆与 CRT 线程数据初始化依赖。
5. `82869F80`，扫描 pre-C 表，非零返回会停止。
6. `82869EA0`，先扫描 pre-C++ 表，成功后扫描 C++ 构造函数表。
7. 后续原入口包含 `82E1F578` 调用；其 main 职责目前只是高置信推断，尚未由本工具执行验证。

四个原指令范围的哈希是入口 `[82868EC0,+1B8)`、表扫描器 `[82869F80,+78)`、
`[82869EA0,+E0)` 和首依赖 `[8286A0D0,+D0)`。原代码中的 `lis/addi` 建立以下边界，
原大端指针数据再由独立生成函数边界集合逐项核验：

|扫描器|区间（右端不含）|slot 数|非零调用|规则|
|---|---|---:|---:|---|
|`82869F80`|`82EA0000..82EA000C`|3|2|跳 0；返回非零停止|
|`82869EA0` 第一段|`831ECAB8..831ECAC4`|3|2|跳 0；返回非零失败|
|`82869EA0` 第二段|`82EA0010..831ECAB4`|864,937|3,873|跳 0 和 FFFFFFFF，按 slot 顺序调用|

前两表的非零入口分别为 `8286E108,828720F0` 和 `8286D748,82878DD0`。
第三表跨越较大的零填充范围，不能根据非零数据边界截断，也不能重排、去重调用。
所有 3,873 个非零项均是已生成函数入口。

阶段 4 恢复的 **299** 个 indexed-native 注册函数全部位于第三表，但只占其子集。
token `1D` 的注册函数 `82E707C8` 位于表 slot `82EA2F0C`；Add_IntInt 注册函数
`82E73108` 位于 `82EA3090`。按手选顺序运行 299 个 native 注册函数不等于标题初始化链完成。

## Verified：原始数据和首依赖的变量 import

原像中的 `8320B718` 和 `8320B728` 均含原操作数处理器 `82508E60`；
`8320B828` 含原 Add 实现 `8250BAF0`。GNatives 地址 `83250D80` 的 4,096 槽在初始化前全部为零。
真实映射原像可取得这些 vtable 数据，无需把原静态字另行复制到输入夹具。

首依赖 `8286A0D0` 的 `lwz` 首先读取 `82000708`，再解引用读出的值。
原展开像中的字是 `00010193`，并且该 slot 明确列于 `xboxkrnl.exe` 的 import records；
低 16-bit ordinal 是 `0193`（403），记录 type 为 0。
同类 slot `82000710` 含 `00010059`，ordinal `0059`（89）。
这些字是 **未绑定 import descriptor**，不是游戏期望的运行时变量地址。
将原像装入而未建立真实 kernel variable export，静态可预测下一次读取地址会是 `00010193`。
这只是本工具的静态候选；实际异常、kernel 模块配置补全及之后的首阻塞由宿主启动实验分别记账。

SDK `rex/system/export_resolver.h` 提供 `ExportResolver::GetExportByOrdinal`、
`Export::Type::kVariable`、`variable_ptr` 与 `SetVariableMapping`。
应优先恢复官方宿主的 kernel/module 生命周期，不能写死 descriptor 为伪地址并声称修复。

## 复现与失败保留

```powershell
python -m tools.research.analyze_startup `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --generated-register local/analysis/phase3/branches-bounded/project/generated/default-disc1/mc2_probe_register.cpp `
  --generated-init local/analysis/phase3/branches-bounded/project/generated/default-disc1/mc2_probe_init.cpp `
  --generated-entry local/analysis/phase3/branches-bounded/project/generated/default-disc1/mc2_probe_recomp.15.cpp `
  --output local/analysis/phase5/startup-disc1-hash-guarded.json
python -m unittest discover -s tests -p test_startup.py -v
```

最终实际输出：`STARTUP entry=82868EC0 mapping=xstart cpp_initializers=3873 native_members=299 static_only=1`，exit 0。
公开合成测试 16 项通过，独立覆盖 branch sign/absolute、表顺序/重复、未知入口、PE 越界、
输出别名、真实 xstart 名称见证，以及两个 CLI 源见证篡改拒绝测试；
源见证失败发生在解码前且不创建结果。不依赖 SDK、cryptography 或原游戏数据。
最初错误地用非 package 的 `tests.test_startup` 执行 unittest，失败记录保留为
`startup-tests-import-failure.log`，后改用仓库已有的 discover 入口。
本地最终报告、指令范围 hash、输入身份与测试日志均在 `local/analysis/phase5/startup-*`。
最终重跑报告为 `startup-disc1-hash-guarded.json`，对应 `startup-hash-guarded.log`
与 `startup-tests-hash-guarded.log`；旧迭代不覆盖。

## 后续有界采样的 GPU 等待链

宿主补齐真实 TOC 与 Coalesced.ini 后，三个独立暂停采样均包含
`xstart -> 82E1F578 -> 82E1F528 -> 82E21740 -> ... -> 8248AE30 -> 8236D318 -> 8236D208 -> 8236CE58 -> 82368E60`。
这是已经进入原 main 路径的运行观察；采样本身不证明永久死锁或完整游戏启动。
原样本来自 `boot-sampled-coalesced/sample-analysis.json`，与纯静态结果分别计账。

只读检查原 PDATA 长度及原始 PPC 指令，交叉核对生成函数，确认：

- `8236D318` 含 `VdInitializeRingBuffer`、`VdEnableRingBufferRPtrWriteBack` 等真实 GPU 命令缓冲区调用。
- `8236D208` 先写 GPU 命令字，再进入 `8236CE58`；后者读取对象 `+10896` 的指针所指 read-progress 字，
  并以 `+10908` 和传入 requested 值构造无符号距离比较。
- 继续循环的精确条件为 `uint32(obj[10908]-requested) < uint32(obj[10908]-*obj[10896])`，
  且 `82368E60` 返回非零。距离条件为假或检查函数返回零均会离开此循环。
- `82368E60` 检查对象 `+10941` 的 bit1；该位为 1 时返回零。
  否则它比较一个由当前线程结构 `+88` 读取的原计数字段与记录值；差值不足 5000 时返回 1。
  达到阈值会调用 `82378F60`，后者引用原 D3D GPU-hang/PIX crashdump 诊断文本。
- `829406D0` 实际读取 `*(*(r13+256)+332)`；它不是宿主时间函数。
  计数字段和线程字段的完整语义尚未核定，不把阈值擅自换算成秒。

这组独立反证把当前采样热点定位为 **GPU 命令缓冲区同步等待**，不是 Coalesced 文本字符解析、
SSE helper 自身故障或分配器循环。实际 read/write-progress 是否恒定、SDK tool-mode 图形环境是否建立，
仍应由只读内存快照及官方宿主配置核验，不以超时强行补写指针或置退出 flag。

原 PDATA 有界反汇编与函数范围 SHA-256 保存为 `stall-original-ppc.json`；
生成实现摘录仅在本地 `stall-generated-inspection.txt`、`stall-helper-inspection.txt`，
静态结论及输入 hash 保存为 `stall-static-summary.json`。这些只读诊断未修改生成函数、原数据或 SDK。

后续宿主实验通过官方 GPU C ABI 的真实初始化/Setup 消除了这道等待：
`boot-c-abi-gpu/title-sdk.log` 已记录命令缓冲区推进以及图形 pipeline/render-target 建立，
随后发现真实缺失的 `MC2Game/Localization/Coalesced.int`。
因此本节 GPU 等待是已保留、已推进的失败阶段，不是当前仍未解决的最终阻塞。
这也反证只增加 timeout 或改写 ring 指针/flags 并非必要修复；仍未声称已有呈现首帧。

## 当前真实阻塞：遗漏的间接回调入口

使用未改原字节的 `game-root-05` 六成员和真实 GPU Setup 后，标题入口继续运行，
在 `boot-fatal-diagnostic/run.txt` 记录 `invalid/unregistered function target=8234FF10`。
fatal 前 PPC `ctr=8234FF10`、`lr=823B9B1C`、对象参数 `r3=40B98DE0`；
调用栈包含 `xstart -> 82E1F578 -> 82E1F528 -> 82E21740 -> 82E203C8 -> 82E38270 -> 82D6CCA0 -> 823A4CA0 -> 823A4BB0 -> 823B99C0`。
这是实际间接调用缺口，不是等待超时、先前 GPU 缺配置或 `.int` 文件缺失的旧失败。

独立原像检查确认 `8234FF10..8234FF40` 是 12 条 PPC 指令、48 bytes 的独立叶函数：
先检查空对象返回，然后将三个原 vtable 地址依次写入对象 `+0x84`、`+0`、`+0x84`，最后返回。
前一段在 `8234FF0C` 以 `bctr` 结束，后一已生成函数从 `8234FF40` 标准序言开始；
所以缺口不是误跳现有函数的内部 label。目标没有 PDATA 记录，也没有当前生成 mapping。
指令范围 SHA-256 和反汇编保存在 `stall-unregistered-target.json`，不提交原像或完整生成函数。

原代码 `82D6C814` 的 `lis r6,8235` 与 `82D6C834` 的 `addi r9,r6,-00F0`
构成回调地址 `8234FF10`，再由 `82D6C844` 调用 `823A6150` 传入。
运行期真正失败的 `823B99C0` 则从来源对象记录 `+284`（`+11C`）取得回调，
在 `823B9B18` 执行 `bctrl`，与 fatal 的 LR 完全一致。
地址构造点到运行期对象槽的完整写入数据流尚未逐步跟踪，不据此赋予类名或构造函数语义；
实际缺失映射、调用地址、空指针保护、三个 store 和原叶函数范围分别有直接证据。

本阶段保留此首个真实生成入口覆盖缺口，不修改生成函数、SDK、对象槽或原像绕过它。
下一阶段应以该原版本为守卫增加显式 entry hint、严格重新 codegen/编译并验证真实回调；
这些步骤仍待执行，而非手写一个空函数令启动继续。
