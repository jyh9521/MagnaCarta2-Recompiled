# 原始 Event imports 与调用 LR 注册表

日期：2026-10-17。本文建立原始导入/直接调用证据，不安装 hook、不覆盖游戏 dispatch、不新增函数 hint、不执行或唤醒事件。

## 固定输入及输出合同

`tools/research/verify_event_import_sites.py` 只接受已有原 XEX/loader 源码的锁 hash 解码路径；在内存得到完整原像后再次锁定 image SHA，再核对 XEX import library/原 16-byte thunk/官方生成注册名。真实 CLI 另要求传入**实际发行** SDK DLL，其 hash 不符即拒绝。原像/密钥不落盘。

- 原 XEX：`26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f`。
- loader source：`36a30e1bc54b9854cbd2572b74e366e733460c5df6edf2b29542de36575858f2`，归属 Xenia 固定 commit，详 [路线 A](EXPERIMENT_ROUTE_A.md)。
- 完整原像：`d18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9`。
- ReXGlue 0.10.0 发行 `rexruntime.dll`：`e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a`。对应头和 SDK/Xenia 归属/许可沿用既有研究，不从 main 分支猜运行实现。

公开函数：

```python
registry = build_registry(original_image, parsed_xex_metadata, generated_register_text)
proof = match_caller_lr(registry, "NtCreateEvent", caller_lr)
```

真实 CLI JSON 的 `registry` 字段就是上述结构。匹配成功只给 `status="validated-original-direct-call"`，未列出/间接调用为 `unresolved-indirect-or-unlisted`，保留 matched=null；类型/身份/完整性错误明确失败。

每个匹配记录包含 `call=LR-4`、原 BL word/hash、thunk/导入名、最多 28-byte 直接前置上下文范围/hash，及原 PDATA 的函数首/排他尾/完整范围 SHA。没有 PDATA 时标记 unknown，不从最近生成符号猜 size。注册表另带 canonical JSON SHA 用于检测意外修改；这是完整性校验，**不是任意自造注册表的密码学来源认证**。

## Verified：八个真实 xboxkrnl imports

原 XEX 均将下列地址登记在 `xboxkrnl.exe` import records 中；每个原 thunk 严格匹配 `{0101ordinal,0201ordinal,mtctr r11,bctr}`，16 bytes 的独立 SHA 保存在结果。官方生成名与实际 SDK `*_entry` exports 各唯一匹配。

|导入名|ordinal|原 thunk|原直接 BL 数|
|---|---|---|---|
|NtCreateEvent|`D1`|`82E8DEDC`|8|
|NtWaitForSingleObjectEx|`FD`|`82E8DF9C`|13|
|KeResetEvent|`8F`|`82E8E32C`|2|
|KeSetEvent|`9D`|`82E8E33C`|9|
|KeWaitForSingleObject|`B0`|`82E8E36C`|8|
|NtPulseEvent|`E2`|`82E8E5BC`|1|
|NtSetEvent|`F6`|`82E8E5DC`|7|
|NtClearEvent|`CE`|`82E8E5EC`|5|

共 **53** 条原直接 BL。没有发现并宣称一个并不存在的 `NtResetEvent` import：本版本的 Reset 是 `KeResetEvent`，Clear 是 `NtClearEvent`。另有 xam 的 `NetDll_WSACreateEvent`，不混入本对象表/kernel event 契约。

### 实际静态 caller LR 清单

下表是原 BL 后的 LR，不是运行次数；这些地址存在不代表本轮都已执行。

|导入|已验证 caller LR|
|---|---|
|KeSetEvent|`823786E4`, `82388330`, `829469C8`, `829479A4`, `8294C8A8`, `82A31674`, `82A31DE0`, `82A322E4`, `82A323FC`|
|KeWaitForSingleObject|`823881A4`, `82388250`, `829469E0`, `82947804`, `8294C8C8`, `82A32288`, `82A32348`, `82A32378`|
|KeResetEvent|`8238827C`, `8294C8D0`|
|NtCreateEvent|`82868B04`, `82868BF0`, `82946658`, `8294D244`, `8294D2D4`, `8294D76C`, `8294DCD0`, `8294DCEC`|
|NtWaitForSingleObjectEx|`82869BC0`, `82941260`, `82941B74`, `82944300`, `829443F4`, `82944668`, `829476F4`, `8294778C`, `8294D0F4`, `8294D184`, `8294D448`, `8294D6C4`, `8294D850`|
|NtPulseEvent|`829423A4`|
|NtSetEvent|`8294249C`, `82945860`, `82945874`, `82945A24`, `8294D3F0`, `8294D69C`, `8294DBBC`|
|NtClearEvent|`829424D8`, `82944620`, `82944638`, `8294CF28`, `8294D800`|

已知真实 wait 样本 `LR=82869BC0` 精确对应原 `82869BBC bl82E8DF9C`；包含它的 PDATA 函数为 `82869B88..82869BEC`（0x64），完整 hash `7441646dd7569ef6cd962af22574f82c827b7a4f2cb3a3d892a313d140e91394`。根阶段的实际 CTR `8248B100` 只与原外围虚分派链相互印证，不替代这里的 import-site 身份。

## 实际 SDK 参数含义，不从 slot/名字猜测

公共 `rex/kernel/xboxkrnl/threading.h` 声明 `xeNtSetEvent(handle, previous_state_ptr)`、`xeNtClearEvent(handle)`、`xeKeWaitForSingleObject(object_ptr,reason,mode,alertable,timeout)` 和 `xeKeSetEvent(event_ptr,increment,wait)`；发行 DLL 的具名 C++ exports 又固定确认各 entry 的指针/整数签名。具体原寄存器合同：

|导入|原 GPR 参数|
|---|---|
|NtCreateEvent|r3=out_handle BE32*；r4=object attributes*；r5=event type 请求（0 manual / 1 auto）；r6=initial state 非零真|
|NtSetEvent / NtPulseEvent|r3=handle；r4=previous-state BE32* 或 null|
|NtClearEvent|r3=handle|
|NtWaitForSingleObjectEx|r3=handle；r4=processor mode；r5=alertable；r6=timeout BE64* 或 null|
|KeResetEvent|r3=guest event pointer，不是 handle|
|KeSetEvent|r3=guest event pointer；r4=priority increment；r5=wait|
|KeWaitForSingleObject|r3=guest object pointer；r4=reason；r5=processor mode；r6=alertable；r7=timeout BE64* 或 null|

发行 `NtCreateEvent_entry` RVA `4193F0` 实际保存原 type/initial 参数；`41949C..4194AB` 将 `type==0` 变为 manual_reset bool、`initial!=0` 变为 initial bool，调用 `XEvent::Initialize`。**命名对象重用分支可不执行该 Initialize**，所以只看到一次 Create 请求或类型参数，不能不看返回 status/输出 handle/是否新建便断言当前 backend reset mode。

本阶段实际发行 ABI 证据：

|SDK entry|RVA|核验范围|SHA-256|
|---|---|---|---|
|KeResetEvent|`419340`|+5E / exact-original-x64-unwind-range|`12aeb37b29d6683685d6eddd9cbfa636905bf77caf782164fe7d98db588496e9`|
|KeSetEvent|`4191C0`|+6D / exact-original-x64-unwind-range|`88a080dc8a296c8053ae2628211f894265cd0edbd05aeed7f4eb9ae3e80086fe`|
|KeWaitForSingleObject|`41A540`|+3B / exact-original-x64-unwind-range|`313f4c83632e605e08e83b857d0a31a36e954625c135ce1d64e9c3a490a7cb6e`|
|NtClearEvent|`419860`|+20 / bounded-prefix-only-no-exact-unwind-boundary|`abd970b2f0a3dc2a8b8bc649be364dd70c6291e3744d7d3114f83ef431bfe90d`|
|NtCreateEvent|`4193F0`|+10A / exact-original-x64-unwind-range|`ad48ca4f82dbf027b20bfca54d5ced0bc375abf7ea114fabbd36cc82464598b4`|
|NtPulseEvent|`4196C0`|+83 / exact-original-x64-unwind-range|`8923f50822e9fad99a5efb229836fd1b0bda3a316e934ee70495296c6a7da5de`|
|NtSetEvent|`4196B0`|+20 / bounded-prefix-only-no-exact-unwind-boundary|`72e8fcc0deda8a983e70d62a8f7b438ba3cfce1a9a379146f7406357ea1f6b1d`|
|NtWaitForSingleObjectEx|`41A580`|+B4 / exact-original-x64-unwind-range|`5ebc7388d77d4cffc683788f9e85a85d061e5c7d34ae2770901243e39c24c818`|

部分 SDK leaf entry 没有 x64 unwind/PData，最初强求所有 entry 都具备完整 unwind range 的做法失败，随后又发现无 unwind wrapper 不一定首条即 jmp；这些失败保留在 `event-import-sdk-contracts.json`。对这两项只报告 32-byte 有界 prefix（可能包含邻接代码），不伪造完整函数末尾。SDK DLL 整体 hash 和具名 export 身份仍严格固定；prefix 不作为独立完整函数边界证明。

### Query kind1 不能代替创建轨迹

[等待对象研究](RESEARCH_WAIT_OBJECT.md) 已保留：公共 Query 返回 kind1 的枚举含义，与实际 backend reset mode 分开；Query(state) 还可能调用 Wait(0)，本研究不会额外调用。已有 `F80000AC / guest3007D018` 元数据本身既不暴露 signal 状态，也不指出创建/Set 的生产者。

## 真实跟踪记录如何与静态注册表对账

这里只匹配跟踪器**实际捕获**的 import name 和 raw original caller LR；实际 handle、guest object、返回 status、线程 id、GPR 和对象创建/关闭时序仍由另外的运行轨迹提供。

- import 与 LR 都一致，才能引用同一个原 BL/hash/PDATA 证据。
- 不能只因 `F80000AC` 数值相同就在跨进程、关闭后复用或不同生命周期之间拼接对象。
- 没有列出 LR 时，可能是间接调用、宿主 SDK 内部调用或未支持场景；不按附近 caller 自动归属。
- 静态 SetEvent caller 列表不是已经执行的 signaler 列表；成功 Set 的返回也不自动表示某一 Wait 必然观察到信号。
- 不覆盖 generated dispatch 或恢复其它入口；实时 delegator 的保存/完整 forward 合同由独立组件负责，不在本工具实现。

## 复现与失败记录

干净 checkout 按既有原 XEX 提取、锁 loader、严格生成流程准备用户输入，然后显式提供五个路径；不依赖旧私有 image.bin：

```powershell
python -m tools.research.verify_event_import_sites --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --generated-register local/analysis/phase11/strict-codegen/project/generated/default-disc1/mc2_probe_register.cpp --sdk-runtime local/upstream/rexglue/sdk/win-amd64/bin/rexruntime.dll --output local/analysis/event-import-reproduction/registry.json
python -m unittest discover -s tests -p test_event_import_sites.py -v
```

真实首轮 `exit=0`，八项计数与上述表一致；22 项标准库合成测试 `OK / exit=0`，不要求 cryptography、SDK 或游戏数据。真实解码路径需要既有 `image_from_xex()` 的 cryptography 依赖；无私有密钥常量进入公开源码。

负例覆盖非 BL、错误 LR/导入、边界/对齐/越界、重叠 PDATA、错误 hash/SDK、bool schema、篡改注册表、错误 thunk、重复原 import record、错误官方生成名和 malformed library。

另一次真正 CLI 对合成 unsupported XEX 的拒绝为 `exit=1`，原文异常 `ValueError: unsupported XEX hash`；输出文件不存在。命令/输入 hash/逐字 stderr 保存在 `local/analysis/phase12/event-import-guard-failure.json`。没有为了生成报告而接受未知版本。

本地 `event-import-original-registry.json`、`event-import-matcher-proof.json`、`event-import-sdk-contracts.json` 和测试日志保留完整静态证据及失败；原 XEX、SDK、旧树和其它代理代码均未修改。以下新增真实轨迹只提升已捕获调用的证据层级，不据静态候选批量恢复或唤醒对象。


## 已验证：buffered FAULT 轨迹与原调用点对账

`local/analysis/phase12/boot-trace-buffered` 的独立重解析保存在 `trace-independent.json`（SHA256 `9d80096e06ba4a82fc97fa31e634ed769964d390409ac1816a4a27e11b3bd6d0`）；记录逐项固定 trace、run、report、host.map、SDK log 和实际 EXE 的 hash。3873 条 ready entry 全部通过 import name + 原始 LR 注册表匹配，parser errors=0、pending=0、dropped=0。这里是 FAULT 期间 `status=installed / frozen=0 / weak_snapshot=1` 的弱快照，**不是**已经恢复、冻结且覆盖完整生命周期的 `capture_verified` 结果；不得把 slot 顺序当作跨线程时钟。

同一进程内数值句柄 `F80000AC` 的已捕获记录如下；post 的 result 均为0：

|调用|pre/post slot|原 caller LR|宿主线程|实际记录|
|---|---|---|---|---|
|Create call48|89/90|`82868B04`|43560（main）|r4=0、r5=0、r6=0；成功读取输出 handle `F80000AC`，只有这一条匹配的成功 Create 候选|
|Set call50|93/94|`8294249C`|43560|同数值 handle，r4=0|
|Wait call51|95/96|`82869BC0`|43560|r6 非空；实际返回0|
|Clear call53|99/100|`829424D8`|43560|同数值 handle|
|Wait call1935|3863/3868|`82869BC0`|43560|r6=0；实际返回0|
|Set call1937|3866/3867|`8294249C`|48148（worker）|同数值 handle，实际返回0|

在固定 SDK ABI 下，捕获的 Create 参数请求**未命名、manual-reset、initially nonsignaled** 事件；这比先前 Query kind1 更直接，但仍没有额外 Query(state)、读取 backend 或全生命周期追踪。先前 Query 字段缺陷的保留说明仍成立。同数值句柄的匹配不排除未捕获 close/reuse；成功 worker Set 与 Wait 返回也不证明这一 Set 是唯一唤醒原因。

原始 LR 的 BL/PDATA/hash 证据之外，actual native frame 用该次 host.map 独立解析得到下列宿主调用链（从 import 向调用者列出）：

- Create：`sub_82868AB0 → sub_8248B068 → sub_8248B198 → sub_8248E118 → sub_8248EB98`，随后经过启动链到 `xstart`。
- main Set：`sub_82942488 → sub_8248B0F0 → sub_8248E118 → sub_8248EB98`。
- worker Set：`sub_82942488 → sub_8248B0F0 → sub_82491930 → sub_82491630 → sub_8248EF08 → sub_82398EB0 → sub_82399090 → sub_82399268 → sub_8248BB60 → sub_8248BB58 → sub_8294CD98`。
- 后一 Wait：`sub_82869B88 → sub_82868B50 → sub_8248B100 → sub_82490300 → sub_82E20F80`。

这些 native frame 名是**最近前置 linker symbol + offset**，不是每个原 PPC 调用边或源代码行的独立证明；具体 RVA、offset 和 frame index 均保留在独立 JSON。它们识别实际捕获的创建/Set 上下文候选，而不是给所有静态 caller 宣告执行。

该次运行22.623s 后捕获 `C0000005 / guest3` fault，SDK log 同时保留 `data_party_start.xxx` 缺失观察。它不是此前 unbuffered 44.523s 重叠 dump：旧失败目录原样保留、不参与当前 caller 结论。两个 Wait 已返回且 worker Set 实际执行，故20s 的相同等待采样不足以证明 deadlock；也不据此宣称干净退出、完整加载或首帧成功。缺文件与后续 AV 的因果尚未由此证明。

独立原盘只读验证另存 `deployment-next-evidence.json`：两盘 `MC2Game/CookedXenon/data_party_start.xxx` 都为3964928 bytes，SHA256 `96e4653fa9b6a02ed124ce7ced22495f97c13e1138cb03b0871567ff1642e31a`；内存中重新解析446/25 header 与1407 names /166 imports /1198 exports。该检查没有部署资源、执行 object payload 或证明运行期挂载路径有效。
