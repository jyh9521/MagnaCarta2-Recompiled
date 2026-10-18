# 开发与测试进展

## 文档分工

[项目首页](../README.md)只保留项目介绍、可用状态和操作入口。本页维护当前研究边界与阶段索引；精确地址、资源身份、实验矩阵、失败记录和回退证据留在对应专项文档，不再逐轮追加到首页。

## 当前决定：原生重编译无限期暂停（2026-10-18）

Windows x64 原生重编译研究正式归档，不再作为近期交付目标。本轮不继续修复 ReXGlue SDK、输入并发、内存异常或资源部署。后续开发转向原版 Xbox 360 资源的简体中文汉化，以 Xenia 为主要验证环境；优先简体中文字形、文本回写与游戏内显示。现有成果仍有效，证据等级和失败记录保持原义。

已完成、已验证、未完成、未解决的分类、固定环境、归档标签和独立实验分支见[归档记录](NATIVE_RECOMPILATION_ARCHIVE_2026-10-18.md)。以下原生阶段内容为历史状态，不构成继续研发指令；GitHub 仓库保持非 Archived 状态，平台归档须另行确认。

## 历史研究边界（2026-10-18）

- 原版 XEX 装载、原入口与部分初始化链已执行；全模块严格构建和多项原函数差分已有独立证据。
- 原 SDK 输出曾读回标题和主菜单；有限自动 START/A 输入已触发 New Game。SDK 读回、可见呈现、物理输入和可玩性分别验收。
- 阶段34独立校验并完整解压`02_village_ter01.xxx`，完成单成员串行交叉与实际删除回退；补回样本后续明确包为`sizesmpl_structures.xxx`。全样本有限部署关联分类为`false`，不等同地图或玩法通过。历史`C0000374`及早期AV继续保留未决。
- A2基线与B3补回均记录SDK读取host `FFFFFFFFFFFFFFF8`的AV，分别exit3221225477/26，没有指定panic；全样本因果汇总不判通过，补充样本不替换失败。
- 序章视频/字幕渲染、电影正常结束、地图加载完成、战斗、存档、换盘及完整通关尚未验收。
- 本地化正式译文、中文字形及界面排版尚未完成游戏内验证；仍需最小可回写本地化验证。

最新实验的完整输入、原包验证、交叉测试、失败与回退见[terrain 单成员研究](RESEARCH_TERRAIN_DEPLOYMENT.md)。没有玩家发布包；单元测试、编译和静态解析通过不改变上述验收边界。

## 阶段36：SDK输入并发门锁与ABI复核

默认关闭、固定SDK hash守卫的host IAT门锁已完成独立SDK压力、真实header夹具及同EXE进程开关交叉。阶段35/36既有无锁样本记录真实访问异常和堆终止；本轮无锁/加锁/撤销/再加锁分别为timeout124/完成0/timeout124/完成0。超时不作为已证死锁，串行通过不外推SDK全局修复。

新host编译与197对象链接均exit0，真实标题执行到45秒观察边界；开启门锁peak1，关闭恢复原导入路径。ABI夹具新增大小/偏移/BE固定字节向量及高32位寄存器保留验证。历史负八读取、早期critical-section AV与堆终止的完整写入来源仍未闭环；首场景、移动和战斗未验收。完整证据、修复覆盖与未决项见[输入串行门锁研究](RESEARCH_INPUT_SERIALIZATION.md)。远程CI本轮未执行。

本轮固定阶段35资源根，不增加、移除或修改游戏资源，不改SDK DLL及生成游戏代码。暂停前的后续候选为同线程、同对象写入轨迹捕获；该候选现已冻结，不再安排原生研发。

## 阶段35资源线记录（独立保留）

资源线仅改变`sizesmpl_structures.xxx`存在状态；独立原盘提取、全段解压、A/B/A/B和复制根删除回退保持同EXE与输入。SDK线单独检查阶段34 A2/B3的原始异常、SDK故障指令和调用路径，不把host AV作为缺包证据。

原包提取、严格表解析与完整解压已完成：物理5111808字节，逻辑16238476字节，1140 exports；串行资源矩阵的历史样本已保留，保守结论见对应研究；归档后不继续运行。A1恢复指定`sizesmpl_structures.xxx`panic，B1到45秒窗口exit26且SDK读回非黑图像；实际查看并对照原`csm_prologue.bik`采样后归为序章视频画面证据，不认定首场景或可移动画面。SDK独立静态核验已定位`rexruntime+117F11`为`vector<DeviceInfo>::clear`内`mov r8,[rcx-8]`，调用者为`InputSystem::RefreshDevices`，GetState/SetState均进入；并发写入来源仍需独立实验，不由两条原日志合并推定。

待验证假设：①缺部署控制指定panic，补回应改变明确失败且删除应恢复；②包结构或压缩异常，独立解析和全解压应失败；③SDK空指针路径可独立产生负八读取，故障指令与源码应吻合；④movie observer影响复现，关闭对照可能改变host AV，有限不重现仍不算修复。首场景、移动、战斗在原生路线中仍未验收；现行优先级改为原版资源汉化与 Xenia 最小验证。

## 后续研究入口

1. 固定原版双盘输入指纹与 Xenia 版本、配置及日志格式，先记录未修改原版的对照行为。
2. 调查原版字体编码、字符映射、图集与 metrics，选择许可明确的字体来源；验证简体字覆盖。
3. 使用小型文本样本完成提取、稳定 ID、控制码保护、回写和结构校验；当前已有提取证据不等于已实现回写。
4. 在 Xenia 对照原版与修改副本，保留截图、日志、文本身份、字形/换行/裁切结果和回退记录。
5. 最小验证通过后再安排大规模翻译。通用工具与 locale 数据分离，原版资源和生成输出仍仅留本地。

这些条目属于后续准备事项，本轮只归档，不安装、升级或运行 Xenia，也不宣称汉化 PoC 已通过。

[已知问题](KNOWN_ISSUES.md)记录运行限制；[技术记录](../TECHNICAL.md)维护实现依据；[实验门槛记录](NEXT_STEPS.md)保留历史路线和前置条件，其旧阶段待办须结合对应结果阅读。

## 阶段记录索引

各阶段文档描述当时输入与观察，不代表当前全部问题已解决。后续阶段可能推进旧阻塞，也可能新增未决失败。

| 阶段 | 研究与结果 |
|---|---|
| 1 | [第一轮验收记录](PHASE1_RESULTS.md) |
| 2 | [第二阶段验收：身份、文本、包引用与两路线实验](PHASE2_RESULTS.md) |
| 3 | [阶段 3：分支恢复、全模块编译与 UFunction 原生调用缺口](PHASE3_RESULTS.md) |
| 4 | [阶段 4：完整宿主链接、原生名称映射与真实 native 调用](PHASE4_RESULTS.md) |
| 5 | [阶段 5：真实原像装载、初始化链与标题首阻塞](PHASE5_RESULTS.md) |
| 6 | [阶段6：原回调严格重生与标题初始化推进](PHASE6_RESULTS.md) |
| 7 | [阶段7：虚分派thunk、原资源启动和比较回调缺口](PHASE7_RESULTS.md) |
| 8 | [阶段8：双返回比较回调恢复与native入口缺口](PHASE8_RESULTS.md) |
| 9 | [阶段9：GNatives[52]网关恢复与扩展入口](PHASE9_RESULTS.md) |
| 10 | [阶段10：61扩展原入口恢复与真实等待边界](PHASE10_RESULTS.md) |
| 11 | [阶段11：真实presenter与等待Event元数据](PHASE11_RESULTS.md) |
| 12 | [阶段12：原事件链、21成员与新原入口缺口](PHASE12_RESULTS.md) |
| 13 | [阶段13：原浮点叶、严格FP合同与下一原入口](PHASE13_RESULTS.md) |
| 14 | [阶段14：双返回原叶、64bit模型纠正与下一原阻塞](PHASE14_RESULTS.md) |
| 15 | [阶段15：原写入、条件尾ABI与下一原阻塞](PHASE15_RESULTS.md) |
| 16 | [阶段16：完整索引尾分派与真实入口推进](PHASE16_RESULTS.md) |
| 17 | [阶段17：完整word-load叶与真实入口推进](PHASE17_RESULTS.md) |
| 18 | [阶段18：原panic实际文件名与header观测](PHASE18_RESULTS.md) |
| 19 | [阶段19：独立原资源部署与可逆真实入口验证](PHASE19_RESULTS.md) |
| 20 | [阶段20：完整byte flag恢复与新资源阻塞](PHASE20_RESULTS.md) |
| 21 | [阶段21：PreF原包部署与可逆真实入口因果验证](PHASE21_RESULTS.md) |
| 22 | [阶段22：voc原包部署与有限运行边界](PHASE22_RESULTS.md) |
| 23 | [阶段23：原延时路径与计数轮询](PHASE23_RESULTS.md) |
| 24 | [阶段24：真实增减回调与流动的队列](PHASE24_RESULTS.md) |
| 25 | [阶段25：真实调用时间轴与标题画面读回](PHASE25_RESULTS.md) |
| 26 | [阶段26：原START输入链与主菜单](PHASE26_RESULTS.md) |
| 27 | [阶段27：原A确认链与下一个真实分派阻塞](PHASE27_RESULTS.md) |
| 28 | [阶段28：恢复8233D3D8原读取叶与确认后黑场](PHASE28_RESULTS.md) |
| 29 | [阶段29：New Game后的电影/伴随字幕状态与独立因果隔离](PHASE29_RESULTS.md) |
| 30 | [02_Village_Persistent：单成员部署与原panic隔离](RESEARCH_VILLAGE_DEPLOYMENT.md) |
| 31 | [Test_PathNode：单成员因果隔离与加载边界](RESEARCH_PATHNODE_DEPLOYMENT.md) |
| 32 | [02_Village_Collision：单成员部署与可逆失败边界](RESEARCH_COLLISION_DEPLOYMENT.md) |
| 33 | [CinookIsland_CompTuto_01：单成员干预、混合失败与加载边界](RESEARCH_CINOOK_DEPLOYMENT.md) |
| 34 | [02_village_ter01：独立部署、完整解压与实际回退](RESEARCH_TERRAIN_DEPLOYMENT.md) |
| 35 | [structures 原包、有限部署关联及失败](RESEARCH_STRUCTURES_DEPLOYMENT.md) |
| 36 | [输入共享门锁、ABI和回退边界](RESEARCH_INPUT_SERIALIZATION.md) |
| 37（追加保留） | [同对象输入并发捕获](RESEARCH_INPUT_CONCURRENCY.md) |
| 38（未完成） | [独立实验分支与本地证据](NATIVE_RECOMPILATION_ARCHIVE_2026-10-18.md) |

## 首页迁移与历史保留

重整前首页的完整正文保留在[README 历史快照](history/README_2026-10-18.md)，包括旧技术总览、工具示例、项目更名及原阶段链接。快照中的历史数值、失败和不确定性不作追溯性改写；当前入口使用本页及专项研究。

## 阶段37：同对象输入异常的独立捕获

固定原EXE、SDK、XEX、197对象、生成树与phase35资源根，源码确认已有门锁实现且默认关闭。新增独立有界trace与外部异常捕获，将同一InputSystem的GetState/SetState线程、API边界顺序、负八AV寄存器和真实unwind栈关联；另采集C0000374释放栈及minidump，不把两者视作同一破坏写入历史。本轮未证实新增未覆盖调用者，生产补丁不扩大。OFF/ON/OFF/ON与压力、源码回退分别验证；exit26、timeout和异常分开，仍未验收首场景、移动或战斗。详见[同对象输入并发调查](RESEARCH_INPUT_CONCURRENCY.md)。该阶段提出的首次破坏写指令捕获方向随原生路线一并暂停。
