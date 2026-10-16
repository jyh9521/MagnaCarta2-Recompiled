# 双光盘布局

## Verified：按盘内路径与 SHA-256 比较
盘 1 为 2016 个成员，盘 2 为 2340 个成员。

|类别|数量|
|---|---:|
|同路径同内容|1631|
|同路径不同内容|3|
|仅盘 1|382|
|仅盘 2|706|

三个同路径不同内容的文件：
- MC2Game/Config/Xenon/Cooked/Coalesced.ini
- MC2Game/Xbox360TOC.txt
- default.xex

完整列表在 local/analysis/phase1/disc-comparison.json，复现命令见 RESEARCH_GAME_STRUCTURE。
比较按精确盘内路径，不将不同路径相同内容直接视为逻辑依赖。

## 尚未验证的依赖
换盘触发、资源搜索顺序、同名覆盖、存档跨盘状态和 TOC 语义尚待分析。
不得直接合并两盘并静默覆盖同名项。后续用 (disc, path, hash) 作为资源身份，保留不同 XEX 与配置的映射。
独有包只能证明分布，不能证明章节或运行时加载关系；需建立包导入/导出图并补充实际运行轨迹。

## 第二阶段：包导入候选的双盘交叉匹配
两盘全部 UE3 候选表通过解析后，按 root Package import 名称与文件 stem 建立候选图。
盘 1：7339 条本盘唯一文件候选、5 条仅另一盘有唯一文件候选、502 条两盘均无候选。
盘 2：8710 条本盘唯一文件候选、709 条两盘均无候选。
“另一盘候选”不是必须换盘的证明；无候选也不直接等于缺文件，可能涉及别名、运行时包或其他未解析机制。
工具：`python -m tools.research.compare_dependencies --help`；完整本地结果为 local/analysis/phase2/cross-disc-dependencies.json。
