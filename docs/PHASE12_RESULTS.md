# 阶段12：原事件链、21成员与新原入口缺口

## 原语义和透明观测

原8个事件导入/53个直接BL、各原PDATA边界/整函数hash独立验证，实际raw LR逐条匹配。
原Create参数ABI为out-handle*/attributes*/eventType/initialState；区分请求与实际backend，SDK Query(kind)不是状态证明。
生成代码直接调用host导入；只替换当前自建EXE精确四个IAT槽，先完整DLL/PE AMD64/唯一导入/GetProcAddress指针/page保护preflight。
四个导入为NtCreateEvent/SetEvent/ClearEvent/WaitForSingleObjectEx；NtResetEvent不存在，不拿KeResetEvent代填。
wrapper原函数exact一次委托，以8192槽锁自由ring记录pre/post、caller LR/参数/结果/安全out-handle与16个native PCs；不写原SDK、XEX、vtable或GNatives。
完整PPCContext、128-byte合成内存、errno/LastError、异常传播、阻塞pre、溢出、冻结、PE拒绝、原IAT指针及页保护恢复均差分验证。
没有SDK对象查询/唤醒/文件I/O发生在wrapper内；native栈采集和原子记录仍有观测开销，不宣称零扰动。

## 严格生成与全量链接

strict codegen exit0；397生成源与阶段11逐文件同字节，只有3项codegen依赖/stamp元数据不同。
新树`ae88b3e9c6506fa6ca9ac42981653c7736975cbc889a1bbced35a5bd74b034b4`精确allowlist，未知树仍拒绝；没有增加入口hint。
197源/58166函数静态审计0 findings，197/197 TU全量重编译与58412映射显式链接通过。
AMD64 PE/map/所有58166生成函数与对象归属独立核对；三个host header全部hash/snapshot守卫。
两盘原ISO全SHA、SDK1193文件、八组1576对象与全部生成树再次核验不变。

## 真实创建、worker调用与Wait返回

清洁20秒 `boot-trace-bounded` 实际21.771秒、exit26；3866条记录、drop0/pending0/frozen1，IAT指针/页保护实际恢复且capture_verified=true。
更长45秒窗口的FAULT快照独立记为weak/nonfrozen，不宣称正常restore或完整采集。
`boot-trace-buffered` 的3873条、`boot-trace-root21` 的4191条均可逐条匹配原import+LR，错误0。
同一运行候选F80000AC的创建与调用可观测为：

- 唯一成功Create候选：attributes=0、请求kind0/initial0、返回status0；原LR82868B04。
- main Set、一次成功Wait、Clear均已记录；随后main再次Wait。
- worker线程在原82942498调用NtSetEvent（LR8294249C），status0；main后续Wait也返回0。
- creator/worker native栈可分别关联原82868AB0/8248B068/...与82942488/8248B0F0/82491930/...；nearest-symbol不是原PPC逐边执行证明。

这些事实否定把旧20秒相同等待样本直接叫作已证死锁；没有为推进而补事件信号。
同数字handle相关性不是完整生命周期证明；NtClose/reuse、SDK内部/缓存函数指针和其它事件导入未覆盖，signal/backend模式及完整生产者依赖图不由本记录单独确定。
详见[原调用点研究](RESEARCH_EVENT_IMPORT_SITES.md)与[IAT研究](RESEARCH_EVENT_IMPORT_TRACE.md)。

## 部署缺失与下一真实阻塞

20原成员根的45秒实际请求data_party_start.xxx失败，随后原guest3 write AV/C0000005，保留部署失败及完整栈。
两盘原包实际读取均3,964,928bytes/同hash；独立LZX/UE3表复核与历史一致。
新建21根，整ISO/成员hash与原输入不变全部通过，只增加该原包，不覆盖20根或创建空包。
新根45秒trace与无hook控制均实际达到：

```text
[FATAL] Call to invalid or unregistered function at guest address 0x82AC1DE8
LR=8266CC78 CTR=82AC1DE8
exit=3221226505 (C0000409)
```

这是原游戏.text入口遗漏，不是SDK导入：原20-byte/5指令叶SHA
`579d0af704a9e2c35ba6dc55ffe769344f780cf91ddc302e77aa72da6071ab53`，无包含PDATA，紧邻边界已核验。
原体从object+0x30/+0x34两次lfs/stfs至r4/r5后blr；caller8266CC74 bctrl经原vtable+0x20分派。
本阶段未加hint，也未执行该原体；r5现场未采集，不捏造参数或属性名。下一项先独立浮点/副作用差分再严格恢复。

## 失败、测试与回退

首次非缓冲5.6MB stdout dump使20秒探针实际44.523秒；真实缺包AV期间两dump交错/截断，capture拒绝，旧误标bounded的报告保留。
首次源码事务保留在verification，修正隔离副本SDK条件skip说明后以新目录verification-final重验；不覆盖前一事务。
修正为独立64KiB缓冲文件、原子status/fixed cutoff、stdout fault记录、SDK AV正证据与预建RVA索引；不改游戏行为来消除日志。
原SDK wrapper缺可推导unwind边界的研究失败和错误XEX实际exit1/无输出拒绝同样保留。

源码基线531→修改575→恢复531均OK；基线/恢复skip2，隔离修改副本/全新clone skip3（多一项本地SDK缺失条件测试）。
实际带SDK根目录575项skip2，固定SDK头合成差分另已执行通过；catalog通过，原字节守卫与真实运行分别记账。
隔离回退恢复162个基线hash、新增文件移除，主目录保持修改态；配旧phase11源码/构建与原20根实际恢复20秒present边界、exit26且无IAT/trace标记。
新21根独立保留，原数据没有被回退工具覆盖。测试后提交/推送、远端HEAD、全新clone和4项CI在交付记录核验。
`local/analysis/phase12/verification-final/`保留MODIFIED_FILE.py、DIFF_FILE.patch、VERIFICATION.txt、可执行ROLLBACK.sh及精确命令/输入/literal输出/退出码。
原资源/生成代码/二进制/完整日志只在ignored local；没有可见首帧、正常游戏关闭、地图/战斗/存档/换盘或可玩性验收。
