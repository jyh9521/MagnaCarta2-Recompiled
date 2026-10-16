# 文件地图

|位置|内容|是否提交|
|---|---|---|
|tools/inventory|只读扫描、双盘比较|是|
|tools/validators|通用本地化数据校验|是|
|tests|自制样本单元测试|是|
|docs|研究、构建与验证文档|是，LOCALIZATION_STANDARD 除外|
|localization/zh-Hans|结构化工作库，当前为空|是|
|localization/source|提取原文|否，说明文件除外|
|localization/review|人工审核规则|是|
|localization/tools|工具入口说明|是|
|locales/zh-CN|旧模板目录占位|保留，不双写数据|
|src、assets|旧模板占位|保留，当前没有运行时或资源|
|local|原版输入、清单、模板备份、回退副本与日志|否|
|research|研究入口；敏感输出在 local|是，private 除外|
|根目录 ISO|用户现有光盘，不移动、不修改|否|
|AGENTS.md|本地工作约束|否|

## 第二阶段新增
- tools/formats：XEX、Coalesced、UE3固定版本只读解析及可选LZX桥接/构建。
- tools/research：Coalesced候选/对照、双盘包候选图、严格ReXGlue复现实验。
- scripts/verify_stage.py：源码哈希守卫、隔离测试及回退证据生成。
- research/xex：与原版SHA绑定的少量分析入口hint，不含游戏代码。
- local/analysis/phase2：真实原文、包引用、第三方编译、生成C++、实验日志、隔离副本与验证；一律不提交。

## 第三阶段新增
- tools/formats/ufunction.py：严格大端446/25字段/表达式framing及native调用候选。
- research/xex/disc1-control-flow.toml：与原版SHA绑定的完整函数/SEH范围元数据，不修改游戏字节。
- tools/research/{probe_branch_codegen,verify_branch_ranges,audit_generated_control_flow,compile_module,probe_generated_branches}.py：重生、独立核验、模板静态审计、全量编译与隔离叶函数实验。
- local/analysis/phase3：修改前源码、失败/成功生成树、197TU逐个对象/日志、UFunction报告、隔离回退和远端证据；不提交。
