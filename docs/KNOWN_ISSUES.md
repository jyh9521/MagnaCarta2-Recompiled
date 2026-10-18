# 已知问题与限制

> 2026-10-18：Windows x64 原生重编译研发无限期暂停。本页原生路线步骤与待办仅作历史复现记录，不作为近期交付任务；现行方向为原版 Xbox 360 资源汉化和 Xenia 验证。参见[技术归档](NATIVE_RECOMPILATION_ARCHIVE_2026-10-18.md)。

|项目|状态|原因/下一验收|
|---|---|---|
|Windows 原生运行|标题初始化部分通过|8234FF10/823C2740已严格重生；C1A0完整比较回调已恢复；52网关已恢复；61扩展入口已恢复；82AC1DE8原浮点叶已恢复；82AC2810双return已恢复；826A9EC8条件tail已恢复；82A3DEA0索引tail已恢复；82B7CCD0原word-load叶已恢复；当前有效terrain补回样本到sizesmpl_structures原panic/guest3；A2/B3另有SDK读host FFFFFFFFFFFFFFF8异常及历史C0000374未决，详见阶段34，尚不可玩|
|中文显示/字体/换行|NOT TESTED|资源编码及回写尚待调查|
|文本提取/回写|部分实现|Coalesced 候选提取与内存往返完成；对象文本/游戏部署回写未完成|
|跨盘游戏依赖|部分实现|已有包表引用/文件候选图，动态加载与换盘语义未验证|
|XEX PPC 代码分析|部分实现|三处致命分支与五组SEH边界已修；其余控制流/异常路径语义未全面验证|
|完整通关与存档|NOT TESTED|尚无游戏运行构建|
|控制码校验|部分实现|初版仅常见占位符，实际游戏控制码待确认|

当前没有玩家发布包。工具测试 PASS 不改变以上状态。
报告需包含镜像/构建指纹、环境、步骤、预期/实际结果及本地日志位置；不得上传完整游戏资源。

Coalesced 中有未确定窄串编码的文档，保持字节可逆但不纳入语言候选；物理行值不等于全部游戏可见文案。

历史：第二阶段三处条件分支曾生成REX_FATAL；第三阶段已由边界配置修复，并以27组隔离输入验证对应路径。其他游戏路径与异常语义仍未运行验证。

UFunction声明/字节码framing已解析；路线B的3056项native声明尚无验证通过的兼容实现，13731个virtual/global/delegate调用点动态绑定未恢复。

第四阶段已实际执行原 token 0x1D/index146 注册函数、重入分支和真实 Add/操作数解码器。原静态vtable的两个指针及内存环境仍由夹具提供，未执行完整XEX数据装载或全部startup链；本阶段不据此宣称完整 VM 或地图加载。

第五阶段已用SDK装载原XEX，移除上述vtable/GNatives输入夹具；正式标题线程已执行原入口、CRT和main路径。
当时首兼容阻塞是未生成登记的 `8234FF10` 间接回调，SDK原fatal仍保留；不是已经修好的缺口。
Headless GPU已消费命令并建立渲染pipeline，但presenter为空，不表示可见首帧、UI/控制器、存档、换盘或战斗验收。
官方C++ `LoadGpuPlugin` 包装路径在本机有fastfail记录，原因尚未确定；公开C ABI加载同一真实插件成功，不据此推断硬件失败。

第六阶段增加原48-byte范围守卫的入口hint，197TU全量重建、原回调5组差分通过；原标题两次推进至未登记`823C2740`虚分派thunk。
该16-byte原目标及下游vtable+12调用尚未执行；原C0000409 fatal保留，无可见首帧验收。

第七阶段823C2740已严格生成、197TU重编译和4组只记录callee的差分通过。缺包AV保留但不当兼容缺陷；
原18成员暂存后两次命中工作线程82C1C1A0的原fatal。该线程栈不含xstart/main，报告观测flags保留false，
此前6成员运行的主线程栈另有原入口/main证明。电影播放与可见首帧未验收。

第八阶段比较回调双return/内部C214经原指令审计、14组完整受控状态差分和197TU重建通过。
原18成员根缺GuidCache的部署AV保留，严格新增第19个原成员后两次到达主线程82509380原fatal；
302个运行期非fallback native较旧299清单多01/52/61三个槽，仍未实现完整VM或可玩性。

第九阶段52网关4组独立差分、197TU全量重建通过；原19根缺TitleMap部署AV保留，
严格20成员原根后两次触发61扩展入口原fatal，下一byte/下游未观察，仍无可见首帧或可玩性验收。

第十阶段61入口严格重生/全量重建及256后缀差分通过；20原成员根两次在20秒后仍运行，
三次采样均在NtWaitForSingleObjectEx链，LR82869BC0。headless持续presenter=null；
等待对象类型/生产者与因果关系未知，不宣称死锁、成功启动或首帧。

第十一阶段已接入真实SDK presenter与隐藏窗口/官方UI loop，presenter-null从对照514降为0。
等待对象类别Event已观察，Query只报告kind1；实际backend reset、信号状态和生产者未验证。
20秒后仍有等待，未证明死锁、正常关闭、swapchain或可见首帧；仅独立无XEX presenter正常清理已验。

第十二阶段45秒原入口追踪捕获worker Set与main Wait返回；旧20秒等待不是已证死锁。
原20根缺data_party_start随后guest3 AV；严格追加原第21成员后，trace与无hook对照均到82AC1DE8缺登记原fatal。
该20-byte原叶尚未hint/执行，原FPR/输出行为待差分；可见首帧/可玩性仍未验收。

第十三阶段82AC1DE8原叶已strict恢复，197TU全量/fp:strict重建后同21根推进82AC2810原fatal。
新原32-byte叶未登记/执行，真实输入/result未知；rawO2的160项差异是已知不支持配置，不是被删除的失败。
Od与O2strict768夹具通过不证明完整PPC FPSCR/异常/NaN硬件语义，更不改变可玩性状态。

第十四阶段82AC2810双返回叶已严格恢复；完整64bit oracle纠正前512失败保留，最终2048通过。
同21根实际到826A9EC8原fatal，该下一候选含store/尾分派，尚未hint/执行；623测试不改变不可玩状态。

第十五阶段826A9EC8原store/条件tail已恢复，2560差分与197TU严格构建通过，同21根实际到82A3DEA0原fatal。
原callee未在fixture执行，当前标题栈也不证明其当次进入/完成；下一72-byte候选尚未hint/执行，641测试不改变不可玩状态。

## 第十六阶段 — 2026-10-17

真实标题目前在82B7CCD0未登记目标fatal；原8-byte尚未执行。WoodSword原包存在但当前21根未部署；两个问题分开记账，没有首帧/可玩性证明。
[阶段16结果](PHASE16_RESULTS.md)。

## 第十七阶段 — 2026-10-17

82B7CCD0原叶已恢复，1536映射对齐夹具完整返回；同21根197TU实际到原82390A70显式panic写guest3/C0000005。fault/MMIO/未对齐与标题实际word值未验证，不改变不可玩状态。
[阶段17结果](PHASE17_RESULTS.md)。

## 第十八阶段 — 2026-10-17

实际panic已关联WoodSword路径，当前21根仍缺该成员；故障后零header不证明原包损坏，也未完成读取因果或部署修复。仍在C0000005 guest3，未到首帧/可玩状态。
[阶段18结果](PHASE18_RESULTS.md)。

## 第十九阶段 — 2026-10-17

22根两次真实到82E078C0未登记fatal；并未恢复该函数或到首帧。21根回退恢复原WoodSword panic；先前更早critical-section坏指针AV未修复，本次未重现。
[阶段19结果](PHASE19_RESULTS.md)。

## 第二十阶段 — 2026-10-17

原byte flag恢复后当前22根在原panic写guest3，实际文件名PreF_VJuto_Base2.xxx，原ISO包有效但未部署。早期CS AV新增只读observer后未重现，未修复上游。仍无首帧/可玩性。
[阶段20结果](PHASE20_RESULTS.md)。

## 第二十一阶段 — 2026-10-17

23根两次停于voc_bt_juto_0.xxx原BinaryFormat panic；其原ISO成员有效但缺部署，尚未做该成员因果干预。早期CS AV五次not_observed，无根因/修复证据。无可玩性。
[阶段21结果](PHASE21_RESULTS.md)。

## 第二十二阶段 — 2026-10-17

24根两次45秒仍running，exit26；当前延时/调度采样边界未证死锁。多项资源缺失与文件查询unimplemented保留，未建立其唯一因果；早期CS AV未重现/未修复，无首帧验收。
[阶段22结果](PHASE22_RESULTS.md)。

## 第二十三阶段 — 2026-10-17

24根45秒仍运行已定位main原counter83265218=2>1轮询，尚需追踪实际减计数/producer。CS覆盖有溢出，旧早期坏CS AV未重现/未修复；无首帧。
[阶段23结果](PHASE23_RESULTS.md)。


## 阶段24：计数与真实回调
[阶段24证据与复现边界](PHASE24_RESULTS.md)：原计数加载0，实际callback持续完成队列项，711/709的余2仅为观察边界；不把晚期2>1采样当固定对象卡死。默认关闭透明RAW observer，保留原body、strict生成体、SDK与24成员资源根；早期AV未重现/未修复，exit26不等于首帧或可玩性。


## 阶段25更新
[时间轴与真实标题guest-output](PHASE25_RESULTS.md)：原SDK已读回并查看1280×720韩文标题/Press START Button，不是仅GPU初始化；可见present、输入与可玩性仍未验收。8286E618是原purecall错误路径，不因非原子队列头读到基表就认定实际执行。独立默认关闭trace/capture，保留原body/SDK/资源及失败。


## 阶段26更新
[原START链与主菜单](PHASE26_RESULTS.md)：有限synthetic START已通过官方SDK/原consumer进入New Game菜单，同设备neutral控制/实际回退仍Press START。默认driver不变，自动输入不是物理/可见窗口/玩法验收；oldword幅度FF与SDK按钮mask0x0010（bit4）区分，原vtablecallback未直接观察。保留失败和原源码回退证据。


## 阶段27：A确认进展与当前失败
真实A已到原SDK/原helper，确认路径触发8233D3D8未登记原fatal，尚未正常进入可玩流程。native C0000409、图像未捕获、早期CS AV未重现/未修复均明确保留；不是物理输入或可见窗口验收。 见[阶段27](PHASE27_RESULTS.md)。


## 阶段28：确认后状态尚未验收
8233D3D8缺登记已通过strict发现恢复；新真实入口45秒native26边界、SDK输出全黑。当前未正常进入可玩流程，movie资源缺失/流程状态仍待因果定位；旧早期CS AV未重现/未修复。 见[阶段28](PHASE28_RESULTS.md)。


## 阶段29：电影加载因果已拆分，地图加载仍失败
同EXE单变量/删除回退证明bik缺失可逆控制原open失败/成功及电影tick；txt是伴随字幕时间轴，其容器0→1但单独恢复仍黑场。bik恢复后实际推进到缺02_Village_Persistent.xxx原panic，未部署该地图包，未验收序章视频画面/完整结束或可玩性。第一份未进入New Game的trace与所有失败保留，后续使用串行实际prologue证据。见[阶段29](PHASE29_RESULTS.md)。


## 阶段30加载边界

`02_Village_Persistent.xxx`的原包校验、单成员部署、串行交叉实验及实际行为回退见[独立研究](RESEARCH_VILLAGE_DEPLOYMENT.md)。原panic文件名变化与正常加载完成分别记账；原生失败和无有效readback的样本保留，不以缺失日志消失作为可玩性证据。


## 阶段31：Test_PathNode独立隔离

原包单成员干预、串行交叉与实际删除回退见[阶段31研究](RESEARCH_PATHNODE_DEPLOYMENT.md)。指定包panic的可逆变化与加载完成分别记账；保留原生失败、无有效readback及弱快照，后续明确失败为`02_Village_Collision.xxx`，未作为已验证根因或可玩性证据。


## 阶段32：下一包失败仍保留

`02_Village_Collision.xxx`的原包验证、两轮单成员交叉及实际删除回退见[阶段32研究](RESEARCH_COLLISION_DEPLOYMENT.md)。补回后推进到`CinookIsland_CompTuto_01.xxx`原panic；仅支持固定输入下的有限因果贡献，不代表下一包已验证、地图完成或可玩性。原生失败、无有效readback和历史失败记录保留。


## 阶段33：下一包及堆终止仍未解决

`CinookIsland_CompTuto_01.xxx`独立原包验证、单成员交叉及实际删除回退见[阶段33研究](RESEARCH_CINOOK_DEPLOYMENT.md)。有效补回样本推进到`02_village_ter01.xxx`原panic；B1的`C0000374`无有效捕获且保持未决，全样本因果汇总不判通过。条件性因果贡献、混合失败与可玩性分别记账，下一包未部署。


## 阶段34：terrain部署与加载边界

`02_village_ter01.xxx`已完成原ISO/member hash、12段完整LZX解压、严格包表、单成员串行交叉与实际删除回退；修改根后续明确包为`sizesmpl_structures.xxx`。全样本有限部署关联分类为`false`，不代表场景加载、移动或战斗通过。全部原生失败及历史堆终止继续保留，下一包因果未验证。 见[阶段34研究](RESEARCH_TERRAIN_DEPLOYMENT.md)。


## 阶段36：输入并发缓解不等于全局修复

原SDK同一InputSystem的并发GetState/SetState在独立探针中出现AV、堆终止或timeout；默认关闭的host共享调用门锁在固定串行样本完成读写，但只覆盖当前EXE三项必需输入导入及存在时的Keystroke。历史负八读取的破坏写入来源仍未直接采集，早期critical-section AV及历史堆终止继续保留。ABI布局夹具和45秒运行边界不证明可见呈现、首场景或玩法通过。详见[输入并发研究](RESEARCH_INPUT_SERIALIZATION.md)。

## 阶段37：负八复现不等于历史写入闭环

独立SDK同对象两线程已直接捕获RCX=0的117F11负八读取，以及另一进程的C0000374刷新释放栈；原始故障、线程、边界trace与minidump分别保留。尚未捕获首次破坏写入指令，不把历史游戏AV/堆终止合并归因，也未证实新的host门锁遗漏。固定游戏OFF首轮出现117F93的C000001D，ON/OFF/ON其余样本为45秒exit26；不是正常游戏退出或可玩性证据。没有新增生产修复。见[阶段37输入并发调查](RESEARCH_INPUT_CONCURRENCY.md)。
