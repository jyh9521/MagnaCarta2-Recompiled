# 宿主 EXE IAT 的事件调用观察

## Verified：范围与固定入口

本轮新增 `src/host/event_import_trace.h`、`tests/test_event_import_trace.py`。
仅 opt-in 修改**当前宿主 EXE**的四个导入地址槽；不修改 SDK、XEX、原生成代码、
guest 内存表、vtable、GNatives，也不以内联补丁替换 SDK 指令。
类型取自 SDK 公共 `rex/ppc/func.h:30`：
`using PPCFunc = void(PPCContext& ctx, uint8_t* base)`。

独立 PE 读取保存在 `local/analysis/phase12/event-import-pe.json`。
固定 runtime SHA256 为
`e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a`。
`InstallEventImportTrace(exe,runtime,verified)` 要求调用者先核验实际已装载 DLL 的完整 SHA；
false attestation 在解析和写入前拒绝。支持 DLL 中实际导出、宿主实际从
`rexruntime.dll` 导入的名称如下，不猜测 C++ 私有符号：

|精确名称|支持 DLL 导出 RVA|
|---|---|
|`__imp__NtCreateEvent`|`0041D750`|
|`__imp__NtSetEvent`|`0041D760`|
|`__imp__NtClearEvent`|`0041D780`|
|`__imp__NtWaitForSingleObjectEx`|`0041D840`|

`NtResetEvent` 在支持 DLL 导出和已检查宿主导入中均不存在。
`KeResetEvent`、`ResetEvent` 是不同入口，未按可互换入口处理。

## 防御性安装、恢复与接口

公共接口位于 `mc2::host`：

```cpp
bool InstallEventImportTrace(HMODULE exe, HMODULE runtime, bool verified);
void DumpEventImportTrace(FILE* output=stdout);
bool RestoreEventImportTrace();
bool EventTraceMemoryReadActive();
```

安装必须在 guest 线程开始之前。EXE 必须等于 `GetModuleHandleW(nullptr)`，runtime
必须等于实际 `rexruntime.dll` module handle。全部预检成功后才写任何槽：AMD64 PE32+、
有界 import directory、精确 DLL、唯一 descriptor、四个精确名称各一次、有效对齐的 IAT、
原指针逐一等于该 runtime 的 `GetProcAddress`，并保存全部四槽的原页保护。
不扫描代码字节找私有偏移。

写入使用 `VirtualProtect` 和 `InterlockedCompareExchangePointer`：相比无条件 exchange，
并发出现未知指针时失败而不覆盖。随后恢复页保护并验证指针。
恢复只撤销仍属自己的 wrapper 指针；未知外部值不覆盖。
除指针外，恢复还用安装前保存的页保护重设并 `VirtualQuery` 核验；不将仅指针相等称为完整恢复。
安装中途失败尝试回退并返回 false，调用者必须保留失败并停止实验。

## 观察记录与证明边界

8192 条固定 append-only ring 使用保证 lock-free 的原子计数及 ready 发布，不循环覆盖。
每次调用先发布 pre，再原样委托原 `PPCFunc` **恰好一次**，返回时发布 post。
阻塞 wait 没有 post 时仍有真实 pre 记录。
记录包括 host thread ID、PPCContext 地址、LR/SP、完整 64-bit r3..r10 参数及 r3 返回。
pre 还用公开 `CaptureStackBackTrace` 取得最多 16 个 native PC；不在线解析符号。
输出当前 EXE module base/size，PC 在其中才输出 RVA，便于离线结合本次 host.map 解析。
不把原生栈 PC 直接视为 guest 地址。

wrapper 不打印、不进行文件 I/O、不申请项目侧动态内存、不调用 SDK KernelState/对象方法，
也不查询 signal state 或等待/置位/清除事件。公开 Win32 thread ID、backtrace、内存元数据读取
和原子操作有测量开销；本实验**不是零扰动**的证明，也不保证平台内部实现没有锁/分配。
观察前后保存/恢复 Win32 LastError 与 CRT errno，不恢复或改写 PPCContext 来掩盖误差。
原委托的正常返回、异常和致命退出仍由原实现决定。

Create 成功返回后才读取原 r3 指向的四字节 big-endian outHandle。
先验证 guest 32-bit 地址范围、指针加法、`VirtualQuery` committed/readable 页和四字节区域，
再以 SEH 防护并发映射变化。只在这四字节读取期间设置 TLS
`EventTraceMemoryReadActive()`，标题 VEH 在此时应继续搜索，让局部 SEH 记录 out_read=0；
原 SDK 委托不在该标志内，不能隐藏委托中的异常。

`RestoreEventImportTrace` 用 reservation 同一个原子的 frozen 高位一次冻结。
后续 pre/post 均不能预留新槽；已预留 writer 仍可能完成发布。
dump 仅读取一次 counter 快照的固定 cutoff，ready 后字段不再改写；未 ready 槽输出
`EVENT_TRACE_PENDING`。因此明确标记 `weak_snapshot=1`，不宣称完整调用史。
容量耗尽只增加 dropped、不影响原委托。标记形态：

```text
EVENT_TRACE status=restored capacity=8192 reserved=N dropped=N reset_export=absent frozen=1 weak_snapshot=1 cutoff=N
EVENT_TRACE_MODULE base=... size=...
EVENT_TRACE_ENTRY slot=N call=N phase=pre api=__imp__NtCreateEvent thread=... context=... lr=... sp=... r3=... r4=... r5=... r6=... r7=... r8=... r9=... r10=... result=... out_read=0 out_handle=00000000
EVENT_TRACE_FRAME slot=N index=N address=... module=own rva=...
```

只有这四个 API 被观察：未观察 NtClose、其他 handle 生命周期和 Ke/Win32/其他原生事件入口。
相同 handle 值可能重用；未见某 NtSetEvent 不能证明没有其他 producer。
caller LR、创建参数、outHandle 与 native caller chain 的观测需以真实标题记录为准。
本独立实验不推测 signal 状态、不自动发信号，也不承诺解决标题等待。

## 有限差分、失败保留和复现

```powershell
python -m unittest discover -s tests -p test_event_import_trace.py -v
```

最终 **9 个 unittest 通过**（exit=0）。其中一个在 Windows 上以真实固定 SDK 头编译/链接
独立 mock，完全不加载 SDK DLL、不执行原游戏；其余为便携公共契约测试。
本机编译/运行精确命令与结果保存为
`local/analysis/phase12/event-mock-dmgh5iwy/{build.json,build.txt,run.json,run.txt}`。
该目录运行 exit=0，输出：

```text
EVENT_MOCK equivalence=4 guards=9 overflow=2 blocked_pre=1 restore=1
```

四种真实 `PPCFunc` 签名的 mock 逐一比较直接调用与 wrapper 调用，核验整个
`sizeof(PPCContext)` 的逐字节结果、128 字节内存、errno、LastError，且 delegate 入口
逐字节核验原始参数/内存未被 observer 改动。另核验委托异常传播与无伪造 post、
阻塞 wait 的 pre、两种容量边界、freeze 后仍恰好一次委托但不增加记录、原保护恢复及未知槽拒绝。
九种 PE 负例（机器、magic、DLL、重复/缺项、原指针、缺 ILT、IAT 越界、缺 terminator、
image 大小）均拒绝且整个合成映像保持不变。

首次真实头编译 `event-header-first` 已通过；随后 stack、保护和 freeze 增量的多次测试记录
保留 `event-tests-*.txt` 与各独立 `event-mock-*` 目录，没有删除失败或覆盖旧结果。
这证明有限观察器等价性与守卫，不是实际标题调用时序、真实 SDK 所有导入行为或游戏验收。

## 实际标题首次捕获失败：缓冲与并发 dump 修正

`local/analysis/phase12/boot-trace-first` 保留首次实际标题 trace。
IAT 安装/恢复成功，记录数 3866、dropped=0；但将约 5.6MB trace 写到无缓冲 stdout
显著延长观察后输出时间（子进程约 44.523s）。同时标题继续运行并请求缺少的
`data_party_start.xxx`，随后发生 SDK guest 地址 3 异常，VEH 再次 dump。
两次输出交错且末尾截断；**该捕获不作为完整、有效时序验收**。
这同时包含部署缺资源和测量输出设计失败，不是通过造空资源或给事件发信号来修复游戏。

有限修正只改变 dump 接口与状态同步：
`DumpEventImportTrace(FILE* output=stdout)` 使用调用者指定的 `FILE*`，
所有 dump 输出通过 `fprintf(output,...)`；调用者在 wrapper 外为每次 dump
创建独立新文件并设置 64KiB 缓冲，stdout 只留路径标记，不让边界/异常两份记录相互交错。
状态字段改为 `atomic<const char*>`，dump 以 acquire 读取，避免与 restore 写状态竞争。
wrapper、原函数委托、ring 记录、安装和恢复逻辑不变。

修正后的 **9 项测试再次通过**，真实 SDK 头 mock 编译/运行均 exit=0。
`local/analysis/phase12/event-mock-kc494t79` 保存最终精确命令和日志；
新增 mock 的 64KiB 缓冲临时 `FILE*` dump、内容读取及 null FILE 拒绝检查。
先前证据全部保留。真实标题重新采样的有效性，以根代理的新目录与独立 dump 文件验证为准，
不能用这个纯合成测试补足失败的第一次标题捕获。
