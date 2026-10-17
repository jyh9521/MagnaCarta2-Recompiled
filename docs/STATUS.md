# 开发与测试进展

## 文档分工

[项目首页](../README.md)只保留项目介绍、可用状态和操作入口。本页维护当前研究边界与阶段索引；精确地址、资源身份、实验矩阵、失败记录和回退证据留在对应专项文档，不再逐轮追加到首页。

## 当前研究边界（2026-10-18）

- 原版 XEX 装载、原入口与部分初始化链已执行；全模块严格构建和多项原函数差分已有独立证据。
- 原 SDK 输出曾读回标题和主菜单；有限自动 START/A 输入已触发 New Game。SDK 读回、可见呈现、物理输入和可玩性分别验收。
- 阶段33的 Cinook 单成员补回在三个有效样本中推进到 `02_village_ter01.xxx` 原panic；缺失基线与实际删除回退恢复原 Cinook panic。另一次 `C0000374` 无有效捕获，保持未决，全样本因果汇总不判通过。
- 序章视频/字幕渲染、电影正常结束、地图加载完成、战斗、存档、换盘及完整通关尚未验收。
- 本地化正式译文、中文字形及界面排版尚未完成游戏内验证；仍需最小可回写本地化验证。

最新实验的完整输入、原包验证、交叉测试、失败与回退见[Cinook 单成员研究](RESEARCH_CINOOK_DEPLOYMENT.md)。没有玩家发布包；单元测试、编译和静态解析通过不改变上述验收边界。

## 后续研究入口

下一资源候选为 `02_village_ter01.xxx`，目前只记录库存身份，尚未独立验证部署因果。新实验应先核验原版成员和固定构建身份，再进行单变量交叉及实际行为回退；堆终止与早期异常继续单独保留，不以无panic或缺少捕获认定加载完成。

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

## 首页迁移与历史保留

重整前首页的完整正文保留在[README 历史快照](history/README_2026-10-18.md)，包括旧技术总览、工具示例、项目更名及原阶段链接。快照中的历史数值、失败和不确定性不作追溯性改写；当前入口使用本页及专项研究。
