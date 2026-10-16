# 宿主等待对象：公共 API 只读观测

日期：2026-10-17。目标是识别阶段 10 三次采样 r3 中的候选 handle `F80000AC`，不是唤醒或跳过等待。当前报告分开记录：原等待指令证据、SDK 公共接口可观测字段、实际调用后的对象快照。本阶段随后已通过公共对象表观测确认 Event 类别；尚不据此赋予渲染 fence、生产者或实际 backend reset mode 身份。

## 已有真实等待证据与限制

阶段 10 `boot-extended` 的原 `82869BBC` 调用 xboxkrnl ordinal 253 / `NtWaitForSingleObjectEx`，现场 LR `82869BC0` 与之吻合；发行 SDK 的宿主等待代码实际调用 `KERNEL32!WaitForSingleObjectEx`。三次相同样本不等于死锁。原 `82490300 -> 8248B100 -> 82868B50 -> 82869B88` 链的有界指令、PDATA、发行 DLL exports/IAT 和 hash 保存在 `local/analysis/phase10/next-observation-original.json`。

该静态链预测 r4=-1 经 timeout helper 变为 NULL、r5=0，即无限 timeout/non-alertable 等待；r5/r6 没有在旧样本中直接采到。原 handle 可能在恢复线程后被关闭、复用或变化；公共对象表快照是 **post-resume 的一次独立观测**，不与暂停瞬间原子绑定。

## 新增接口及调用合同

```cpp
#include "src/host/wait_observation.h"
mc2::host::ObserveWaitObject(kernel, sample, candidate_handle, sdk_identity_verified);
```

`SampleThread` 只在原等待 LR/CTR 组合 `82869BC0 / 8248B100` 符合当前证据时，将先前采集的 r3 作为候选 handle。必须先 `ResumeThread`，再调用观测函数；不在暂停目标线程时阻塞获取对象表锁。

- header 用 `global_critical_region::TryAcquire()`；锁忙则输出 `status=busy`，不等待、不阻止目标继续运行。
- 成功后使用官方 `ObjectTable::LookupObject<XObject>` 和 `object_ref` RAII。类型特定数据再使用类型检查过的 `LookupObject<XEvent/XSemaphore/XThread>`；没有 class layout 猜测或 private offset。
- 在锁内仅复制固定大小元数据、做最多 128 name-byte 的 hex 转写和公开 getter；所有 retained refs 在锁内释放，解锁后才 `printf`。不在 critical region 中进行日志/文件 I/O。
- 不调用 `Wait/Signal/Set/Pulse/Reset/Clear/ReleaseSemaphore/Save/Delete`，不写事件/信号量/guest 内存，不修改采样寄存器。临时引用计数增减与短暂锁竞争本身仍是观测开销，不能称为绝对零扰动。

### SDK 身份不是由 header 自证

`kWaitObservationRuntimeSha256` 固定为发行 `rexruntime.dll` 的实测 SHA-256：

`e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a`

header 的第四参是**父进程验证证明**：入口探针在构建前核对 SDK DLL，匹配才在子进程环境传 `MC2_WAIT_SDK_SHA256`；宿主将该值与常量一致性比较，并依赖父探针既有实际 DLL 路径与 SDK 树前后身份复核。header 自身没有重新散列正在执行的 DLL，也没有读取/验证全部 SDK 文件；不能把 bool 当作进程内密码学自认证。直接无证明启动传 false 时，只输出 `unsupported-sdk`，不调用对象 API。

## 可观测字段，不把 unknown 变成零

|对象类别|公开只读字段|明确仍未知|
|---|---|---|
|所有对象|`type()`、`name()`（有界 hex）、`guest_object()`、`is_host_object()`、handle aliases/primary|host pointer refcount、handle refcount、生产者/等待图|
|Event|仅 `Query(&type,nullptr)` 所报告 kind（0 manual / 1 auto 枚举含义，非实际 backend 模式实证）|当前 signal state、等待者数、哪个线程将 Set|
|Semaphore|`maximum_count()`|当前 count、等待者、Release 生产者|
|Thread|`thread_id()`、原子 `is_running()`|线程是否活锁、当前等待依赖、未来进度|
|其它类型|通用字段|没有为未知类型扩大私有 layout 读取|

pointer_ref_count 与 ObjectTableEntry.handle_ref_count 在官方头中为 private 且无只读 getter。本工具不使用 guest `X_OBJECT_HEADER` 的计数字段冒充实际宿主引用数。`X_DISPATCH_HEADER` 的 wait-list 字段还用于运行时 handle/signature stash，不能把它们直接当完整 Windows waiter 链。

输出以 `TITLE_WAIT_OBJECT` 开头；`event_signal_known=0`、`semaphore_count_known=0`、`refcount_known=0`、`producer_known=0` 恒定显式保留。`event_type` 等默认数值只在对应 `_known=1` 时具有观察意义；`status` 不是 observed 时，所有默认字段都不作为事实解释。

## 重要陷阱：Query(state) 并不是无扰动查询

已对上述发行 DLL 的 **实际字节** 和 PE export `XEvent::Query` 核验，不仅依据接口名字：

- 导出入口 RVA `253A20`；有界代码 `+0x55` SHA-256：`3037b6fa6670cff1d33a07aa5077450b88d1c06bdfc0c85799550df13941773c`。
- `253A3A` 检查 out_state，null 路径在 `253A3D` 直接跳至 `253A57` 返回，只读 Query 的 kind 标志、写调用者自己的输出变量。
- 非 null 的 out_state 路径在 `253A48` 调用 `rex::thread::Wait(..., false, 0)`；成功后经 `253A71` 的 event 虚调用恢复信号。即便最终恢复，期间也可能消费 auto-reset signal、改变唤醒公平性，故不用于只读状态观测。

新代码只出现 `event->Query(&snapshot.event_type, nullptr)`。没有直接读取该 DLL 反汇编中出现的私有 offset，也没有通过 Wait(0) 猜 semaphore/event 状态。

核验过的官方头 SHA-256：

|SDK 头|SHA-256|
|---|---|
|`rex/system/xobject.h`|`a6bb24d43aea373e0ced84fd3b4edeb4ad2ee57c092308604b5d32796f1f0f6e`|
|`rex/system/xevent.h`|`4cae57e08e859dcafbce253e2619d772db8df6e7247e70251a96bf53a2f28f4d`|
|`rex/system/xsemaphore.h`|`994d5faf4ac4bc2100a49545feb910bf2dac528b5a26f990b21e695567153196`|
|`rex/system/xthread.h`|`4d5ffbe5b62c4aabb202a95f3dbcc90059462f22ae53d652f14741a83572dd0a`|
|`rex/system/util/object_table.h`|`3cd8296dbfe94c4676d182baf82fab9125acd1f36e9469ba31e5ace66edf09cc`|
|`rex/thread/mutex.h`|`c30a48097e9216ea54b93ce599fc122646e54bbdeae36335f71ef8bc907a79d4`|

对象表/API 归属沿用 ReXGlue/Tom Clay 与 Xenia/Ben Vanik contributors，官方 SDK 0.10.0 头与发行 DLL 固定身份；没有下载 main 分支实现替代发行版本证据。

## 验证记录与复现

`python -m unittest discover -s tests -p test_wait_observation.py -v`：8 项。默认无 C++ 编译器 PATH 时，7 个源码合同检查通过、1 个合成编译执行测试明确 skip；没有把 skip 当执行证明。

本机另使用既有 VS x64 环境与便携 Clang 20.1.8，临时在**该测试进程 PATH** 加入编译器，8 项全部通过，无全局 PATH 改动。合成对象表测试覆盖 SDK 未证明/无 kernel/非法 handle 不查表、not-found、typed Event/Semaphore/Thread 字段、event signal 保持、busy-lock 不等待、名称中的换行有界编码。它是自制 API mock，不冒充真实 SDK 对象执行。

此外，`wait_observation.h` 使用真实 SDK 全部头单独 compile-only，`exit=0` 且诊断日志为空。这个检查只证明实际 SDK/编译器接口兼容；实际 `F80000AC` 对象身份必须由根阶段调用后输出核验。

- `local/analysis/phase11/wait-query-sdk-proof.json`：发行 DLL Query 字节、反汇编、固定 DLL/hash 与头 identity。
- `local/analysis/phase11/wait-header-compile/{result.json,compile.txt}`：真实头 compile-only 命令、输入 identity、exit。
- `wait-header-tests-compiled.txt` 保留初轮 mock 断言把换行误当字面反斜杠的失败；修正测试预期为真实 `0A` 后，`wait-header-tests-compiled-final.txt` 为 8 tests / OK。

父阶段负责在真实同版本进程中调用并保存观测；本组件不单独启动游戏，不恢复未知回调、不升级 SDK、不关闭/唤醒等待对象。

## 生产者与当前边界

对象名字或类型可用于提出后续证据查找方向，但没有 event-owner/signaler 的公开只读注册图。`IssueSwap: presenter is null` 只表示当前 presentation 配置/执行边界，不能凭它认定采样 handle 属于渲染 fence；同样不能凭当前 wait 反推具体 I/O、加载、任务或 GPU 生产者。

下一证据应保持原行为，分别观察其它真实线程进度与实际 event/handle 创建/传递链；没有这些证据前，不得通过 Set/Reset、伪造信号或成功 return 绕过等待，也不把三次相同样本宣称死锁或游戏已正常进入首帧。


## Verified：两种真实运行中的公共 Event 元数据

已独立重开 `boot-wait-observed` 和 `boot-present` 各自的 `title-entry.json / run.json / run.txt / title-sdk.log / host.map`，逐项核对报告中的 size/SHA、进程 exit/log SHA、原 XEX、parent_attested=1 与三组原寄存器候选。直接从原日志重新解析三条 `TITLE_WAIT_OBJECT`，与报告结构逐项相同；不只信任报告里一个布尔值。

两种模式各有三条 post-resume 快照，字段均为：

```text
handle=F80000AC status=observed type=2 type_name=event guest=3007D018
host=0 primary=F80000AC aliases=1 name_hex=- name_truncated=0
event_type_known=1 event_type=1 event_signal_known=0 refcount_known=0 producer_known=0
```

因此**公共对象表确认该候选为 Event 类别**，无名字、一个已报告 handle alias、host_object=false。`guest=3007D018` 是公开 getter 给出的 guest object 地址，不是本工具私自读取其内部内存。名字空、alias 数或三个相同观察都不能识别具体用途或 Set 的线程。

### Query type=1 的细分证据与保留项

发行 DLL 的 `XEvent::Query` 用存储的 manual_reset_ 标志 XOR 1 生成 out_type；因此记录的 1 按此 API 枚举意图表示 auto-reset kind。`InitializeNative` 的两条发行代码路径进一步印证：`2539A2` 存 flag1 并调用 CreateManualResetEvent，`2539C0` 存 flag0 并调用 CreateAutoResetEvent。

**但这不作为实际宿主 backend 为 auto-reset 的最终证明。** 对同 DLL 的完整普通 `XEvent::Initialize` 函数（RVA `253910..253983`）作独立字节审查，观察到它按参数选择 manual/auto backend，而该检查范围没有更新 Query 读取的 flag（constructor 先默认置 false）。本次没有捕获 F80000AC 的创建调用路径/参数，所以公共 Query 的 type1 与 backend reset mode 必须分开。这个差异作为后续 SDK 行为核验问题保留，不在本阶段改 SDK、补私有 offset 或通过信号操作来“确认”。

`wait-object-independent.json` 保存 Query、constructor、Initialize、InitializeNative 的完整有界字节与 SHA。结论用语固定为：**“已观测 Event；Query 报告 kind1；backend reset mode、当前信号、引用计数、生产者仍未验证。”**

### 两模式比较不是死锁或首帧验收

|模式|进程时间|观察结束|presenter-null 日志|公共 Event 元数据|
|---|---|---|---|---|
|headless|22.441 s|exit26 / bounded observation|514|三条一致|
|presentation|21.781 s|exit26 / bounded observation|0|三条一致|

开启 presentation 后，官方展示路径初始化与 loop 进入/退出都有记录，该对照中 presenter-null 从 514 条降为 0；相应公共 wait 元数据仍一致。这只表明 presentation 路径消除了本次 null-presenter 诊断，**没有证明等待由/不由 GPU 造成**。展示报告仍明确 `surface_verified=false`、`visible_frame_verified=false`、`title_shutdown_verified=false`。

两个独立进程里的相同 handle/guest 数值不表示同一个跨进程共享对象，更不表示对象状态持续不变。两次仍以宿主观察边界 exit26 结束，没有将持续等待或 error 数量当作游戏成功/死锁结论。

实际证据身份：

|模式/输入|SHA-256|
|---|---|
|`local\analysis\phase11\boot-wait-observed/title-entry.json`|`290984f31817f21f93ea9eef779cee8a3871fbf092d148499443dee081e7a3fd`|
|`local\analysis\phase11\boot-wait-observed/run.json`|`a379ba5a2729ef244031ca086abecf181b52102bb7a4c574cadafff487c39f75`|
|`local\analysis\phase11\boot-wait-observed/run.txt`|`ca548aa26c1e1c897c6ec3dfca8c9c9980b17c1089d5f26f29867144589011e1`|
|`local\analysis\phase11\boot-wait-observed/title-sdk.log`|`ae618a96547217a7d74baaf29bbf0477d822e341f3d07e0ccaa888891c2dbfd4`|
|`local\analysis\phase11\boot-wait-observed/host.map`|`192bd0205749bfda8ed367835ae7823ee268a9f9fa0db1ab8bdd08bcac03c4be`|
|`local\analysis\phase11\boot-present/title-entry.json`|`827ea8e28a44d0ae6b1e5ee96eff12c3d92c27cf1eaff26b28ef33e3ba2ac6e3`|
|`local\analysis\phase11\boot-present/run.json`|`08d21272bdff90abeb13a063f725a82b844ee78fd917fec69dce7ab003391366`|
|`local\analysis\phase11\boot-present/run.txt`|`86c3fb622cadac89d5a17886bf52a7c866fb2cbd13e9e8a739b9fe088e377960`|
|`local\analysis\phase11\boot-present/title-sdk.log`|`e5924136ab07654e09e13545e3182b89f6bcf05280aa59d09e0f27196d37c74c`|
|`local\analysis\phase11\boot-present/host.map`|`192bd0205749bfda8ed367835ae7823ee268a9f9fa0db1ab8bdd08bcac03c4be`|

本地 `local/analysis/phase11/wait-object-independent.json` 是本次只读独立复核的完整结果；原 SDK、公开 header/tests、对象和游戏运行状态均未修改。下一步仍需原创建/传递或实际工作线程的独立证据，生产者保持未知，不凭窗口/事件名字或日志时间关联直接补事件信号。
