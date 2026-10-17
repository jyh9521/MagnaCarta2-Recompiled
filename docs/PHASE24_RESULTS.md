# 阶段24：真实增减回调与流动的队列

## Verified
独立验证原82399650完整0xE4、82399738完整0x2C、822D0A68完整0x9C、consumer82399090完整0x1D4及原table82153638的12字节；227个BE32身份守卫失败即停止观察。SDK RAW强符号包装直接及映射调用，恰好委托原`__imp__sub`一次，不改游戏body/SDK/vtable/GNatives，不强减计数。
原83265218加载初值0。带队列观察的45秒真实24成员根窗口，711次目标增计数、711次成功reservation、709次实际82399738回调，回调LR823990FC，返回8；所有已消费对象与此前reservation FIFO相配，无unknown/drop/suppressed。余2对象是边界上的最新对象，不是固定旧对象永不消费。
92个非原子周期样本跨度45625ms：45次empty、47次捕获，读写游标各65个不同值，最后12样本中连续11次读写游标变化。头对象slot+4分别指向8277B6D8(32)、8286E618(11)、82399738(4)；这些是原表读取证据，不是前两个函数的实际执行证明。独立核验8277B6D8完整0xB4、生产者8277B1F8完整0x3A4、callee8244A360完整0x3E8；该队列项处理后返回12，由consumer对齐推进16，不直接减少主counter。

## 修正阶段23的解释
main同一线程/SP反复经过LR82E20800的增计数调用，实际callback持续把计数降低，生产者又补入新项。阶段23稀疏轮询快照的2>1不能证明同一次wait一直卡45秒，也不能证明整个队列停死。当前已定位的上游是反复生产/完成的队列流水，晚期采样命中2的忙等待相位；确切吞吐瓶颈、可见帧与完整游戏进度仍未知。该观察不足以支持完成或修复结论；未通过手写计数、忽略fatal或延长timeout改变执行结果。

## High-confidence deduction / Unverified
原tick82E20568内207FC增计数→20808调用poll→2080C后续工作→209D0尾helper返回；唯一tick内部回边209BC→2090C位于poll之后。外层82E1F528在F550调用tick，F554读8325DA58，F55C条件回F550。结合711次同线程/context/SP的实际调用，前710轮poll已返回是原CFG+调用时间序的高置信推断，不是710条直接poll-return日志；最后一轮是否已返回仍未知。

## 观察边界与早期AV
counter pre/post是非原子只读快照，不是CAS线性化或所有写入者证明；冻结不代表线程静止。每target8192记录，队列最多128样本，unknown/drop/pending显式保留。默认关闭`--trace-counter`，启用要求SDK/profile/原body/绑定身份匹配。
consumer仅在观察边界按实际callback记录的host线程+creation time+context身份取样，原生Suspend/Resume配对，先Resume后格式化/模块查询；不写guest寄存器。watch窗口实际PC位于新observer的VirtualQuery/ntdll路径，残留PPC LR/CTR不是原游戏阻塞位置证据。最终重编窗口则捕获generated sub_82863DD0内部native PC，两窗口位置不同；raw native stack不是完整unwind。单个暂停点不定位长期瓶颈。采样本身扰动调度，不能当无扰动性能验收。
旧RtlEnterCriticalSection_entry读取坏CS00430036+18的AV未重现/未修复；有效oldLR调用、普通临界区返回、槽overflow与历史坏地址继续分开记账。

## 构建、测试与可逆性
复核未变strict生成树58171函数/58417映射及历史197对象；本阶段另外实际对全部197TU以/fp:strict重新编译，再新编host、显式全量链接、运行真实入口。没有生成体修补或原资源修改。所有标题exit26均为45秒有界观察退出，不是正常guest退出、首帧或可玩性。
源码基线/修改/隔离回退、sameEXE on/off/on/off实际行为回退、恢复源码host重编与真实入口、公开测试/catalog、远端clone及同提交CI均单独记账。精确命令/输入/原始stdout/exit/hash及保留失败存于ignored `local/analysis/phase24`，四件套在`verification-final`。原资源、生成代码、EXE/SDK/object不入库。

## 下一窄门槛
给原main每轮完成、提交/呈现与真实渲染consumer建立同一时间轴；独立验证原8277B6D8→8244A360及8286E618的完整语义后，再做有限实际执行/返回观测，区分正常帧流水、背压和可见帧缺失。继续等待精确旧AV重现及原对象写入历史，不对未观察到的失败宣称修复。
