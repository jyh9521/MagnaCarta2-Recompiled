# 82869800：延时、轮询条件与正常临界区

## Verified：原范围与条件
固定Disc1 XEX SHA256 `26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f`，独立解码与PDATA核对原82869800完整0x90 bytes，SHA256 `2dbea5ab8a504a242f7eedcc5f2fa51e90e8eff79b2259090119f08c2009ebb1`。r3.low32为毫秒，-1分支写8000000000000000；其它值先零扩展32位再乘-10000，写BE64栈interval。r4作为alertable参数；只有low8非零且原SDK返回257才回到原调用。完整body/直接B、BL引用扫描及42个有限整数oracle保留；oracle不等于完整PPC执行或原机计时证明。
原82399778完整0x68比较BE32[r31]与r30.low32，无符号大于时反复li r3,0→828684C0→82869800。真正退出条件是word<=threshold，不是“睡满45秒”。main原82E20808调用的阈值为1，counter为原r29+28；原82E205D8/205E0把该r29设为832651F0，因此对应83265218。

原delaySP+58/+60分别保存caller r30/r31的BE64，+68为BE32 callerLR；两层栈帧0x70+0x80与原helper8286F41C完整20bytes独立核对，delaySP+E8为poll入口保存BE32 LR。observer仅在SDK调用LR82869854、savedLR823997AC和完整原body守卫通过后解释counter/threshold；parentLR82E2080C进一步确认main调用，而不是其它13处直接引用。

## Verified：真实24根的直接运行原因
原host基线45秒exit26。新增默认关闭的host-IAT observer，仅透明委派原KeDelayExecutionThread/RtlEnterCriticalSection/RtlLeaveCriticalSection，SDK、游戏生成体、原vtable/GNatives、资源均不改。完整197个strict对象重验后只重编host并全量链接58417映射。开发首窗口和增加parentLR后的最终窗口全部保留，不把不同EXE说成同一配对。
最终on1窗口55个晚期样本（18844..45500ms）实际观察到：

|字段|值|
|---|---|
|原poll入口保存LR|82E2080C|
|counter指针|83265218|
|BE32 counter / 无符号threshold|2 / 1|
|原比较结果|2>1，继续轮询|
|SDK interval / alertable.low8|0 / 0|
|83263ACC原global word|1，不称对象指针|

该窗口SDK delay共20463778次进入/返回，选中post返回值为0。**45秒仍运行的直接原因已收窄为main原计数轮询条件未满足并持续零延时让步，不是某次KeDelayExecutionThread阻塞45秒或alertable/257内部重试。** 55次稀疏、非原子读取不证明每个瞬间counter恒为2，也不证明延时接口的所有平台语义已正确。

## 原生产者边界：Verified静态，运行根因未定
原82399650对counter原子+1；global83263ACC为0走自身原子-1，非0分支关联8-byte对象，写原table82153638与counter指针+4。原table静态关联82399738；该0x2C叶执行lwsync/lwarx/stwcx原子-1。它是已核验的潜在减计数回调，不代表当前回调实际执行、具体对象/任务名字或生产者缺失已证明。
其它线程大量零延时调用也有不同原caller：823BF0B8与BE32[r30+4]==0条件关联；823991E8来自另一个队列字段比较/全局分支，不可当成同一个main counter。下一最窄缺口是83265218的增减生命周期、该table回调的实际dispatch与生产者进度；保持原counter与调度语义；改变计数或延长超时不构成修复证据。

## 正常CS与早期AV分开
原822D2640进入CS使用inline entry+12，LR822D2674；离开LR822D26A0。它与早期823BF278的BE32[entry+8]+4不同。真实正常4000077C调用多次有返回，选中pre/post配对不支持把一个短暂CS采样直接称死锁。
SDK+10为原生LE atomic lock原字节，trace x0只是其BE字节表示，不能作BE锁计数；+14为BE recursion，+18为owner guest KTHREAD pointer。独立编译SDK public getter确认guest_object()为对象+58，thread_id()为+90，故owner不是host thread ID或public thread_id。pre三word分开读取，可能跨线程变化；无post CS快照，不把组合不一致当损坏或证明已清owner。
真实首窗口oldLR823BF2B8也出现有效CS40BE9304：聚合3次返回，但仅1组完整采样，不能称3份快照。旧坏00430036 AV本组未重现；精确只读AV observer持续开启，没有根因修复结论。

## 观察器与覆盖限制
每API最多64个key，每key128个500ms桶，只采首个pre/post；总API计数独立于key槽。最终on1 CS槽溢出895878显式保留，delay槽无溢出。没有宣称完整CS/所有线程覆盖。冻结仅停新观察，已进入的delegate仍可发布；weak snapshot不是quiescence。`coverage_complete`始终False，pending或pre/post不等也不能自动等同死锁。
wrapper保留输入/原API输出PPC context、errno、LastError，原delegate恰好一次；mock完整context/memory差分、throw透传、PE负例、45秒桶及IAT pointer/protection实际回退验证通过。采样hook只读预flight+ReadProcessMemory，排除MMIO/物理alias/guard/noaccess，失败不暴露prefix；不查询或消费wait状态、不调用TryEnter、不写guest。mock不是真实AV重现或游戏验收。

## 复现和可逆性
```powershell
python -m tools.research.probe_title_entry --help
# 完整原SDK/生成树/197对象输入守卫照常；诊断运行增加 --trace-schedule
```
--trace-schedule默认关闭，要求固定原profile/SDK/完整原body guard；旧source缺对应header明确失败。原panic捕获是独立模式，其请求成功不等于游戏启动；同时诊断无panic的有界窗口时使用execute API保留各子结果，不改变既有CLI panic成功条件。
最终同EXE、同24资源根仅切MC2_SCHEDULE_TRACE：on1→off1→on2→off2，两次off实际恢复无schedule hook/trace的有限观察行为；原host基线和源码隔离恢复后另实际编译链接/运行均保留。精确输入、raw/native exit、失败RED、hash与四件套位于ignored local/analysis/phase23；公开仓库不含原包、游戏生成体或二进制。exit26是host有限观察退出，不是guest shutdown、首帧或可玩性。

最终独立审计发现claimed桶全部截断、flags超宽/未知bits与post原参数矛盾可能误报capture；实际24tests/5fail RED保留，补每key已报告桶计数、低8flags和不可变参数配对守卫后24tests GREEN。首轮812测试事务及已恢复227源副本保留，最终817测试源码事务另存verification-final；既有真实raw重解析不得放宽。
