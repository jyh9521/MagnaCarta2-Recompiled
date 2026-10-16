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

## 第四阶段新增
- src/host：自编SDK宿主初始化与受控native实验，不包含原游戏生成函数体。
- tools/research/{link_module,native_registration,probe_native_call}.py：全量链接、原生名称映射和真实调用验收。
- local/analysis/phase4：源码基线、原件哈希、SDK/对象输入身份、失败迭代、宿主PE/map、原生表、运行/隔离回退证据；不提交。
## 第五阶段新增
- src/host/{image_probe,title_probe}.cpp：真实SDK装载/原数据native实验与有界标题诊断；不含原游戏生成body。
- tools/research/{probe_xex_image,analyze_startup,stage_runtime_files,probe_title_entry}.py：全映像核对、静态初始化链、显式原资源部署、调用栈与首阻塞验收。
- local/analysis/phase5：原源码基线、SDK加载快照、staged只读原资源、全部失败/采样/首次fatal、独立重放与源码回退；不提交。

## 第六阶段补充

- `research/xex/disc1-callback-entry.toml`：原版本48-byte入口发现元数据。
- `tools/research/probe_callback_codegen.py` / `verify_callback.py`：严格重生与有限PPC/原生成体差分。
- [阶段6结果](PHASE6_RESULTS.md)、[重生实验](EXPERIMENT_CALLBACK_CODEGEN.md)、[回调研究](RESEARCH_CALLBACK_ENTRY.md)。

## 第七阶段补充

- `research/xex/disc1-virtual-thunk.toml`：已实际到达的16-byte原入口metadata。
- `tools/research/verify_thunk.py` / `tests/test_thunk.py`：有限候选调查与外部分派录制差分。
- [阶段7结果](PHASE7_RESULTS.md)、[生成实验](EXPERIMENT_THUNK_CODEGEN.md)、[虚分派研究](RESEARCH_VIRTUAL_THUNKS.md)。
