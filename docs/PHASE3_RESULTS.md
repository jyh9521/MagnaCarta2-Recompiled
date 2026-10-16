# 阶段 3：分支恢复、全模块编译与 UFunction 原生调用缺口

本阶段只记录实测结果；游戏链接、启动、首帧和中文显示仍未验收。

## 已验证的结果

|项目|基线|修改态|
|---|---|---|
|公开源码测试|146 tests / OK|233 tests / OK|
|完整生成模块实际编译|197 TU 尝试，192 成功、5 失败，exit=1|197/197 成功，exit=0|
|生成控制流静态审计|3 个 unresolved-branch fatal、10 个缺标签 goto，exit=1|58,162 函数、197 TU，0 finding，exit=0|
|真实生成叶函数执行|旧生成分支不可据此验收|2 个完整函数、27 个合成内存用例与独立 PPC oracle 相同，编译/运行 exit=0|
|两盘 UFunction|阶段 2 尚无解析器|每盘 12,901 个元数据与字节码 framing 均通过，两盘报告相同，exit=0|

三处条件分支为 `82CE6768 -> 82CE6754`、`82CE6774 -> 82CE6754`、
`82DA34A4 -> 82DA3494`。修复对象是生成器函数范围配置，不修改原始 XEX 或 SDK，
也不删除 fatal 或添加空实现。整个模块编译又暴露五组 SEH funclet 边界合并错误，
依据 15 条 PDATA 记录分开配置，避免把两字异常元数据解码为 PPC。
所有 197 个对象均重新编译，独立检查为 AMD64 COFF，共 164,949,567 bytes。

最终生成树 SHA-256：`2f665e02be216bc4e87ed8544bd29bf2d0b24dde92857506b492bd18056a43db`。
对象集合 SHA-256：`9b404d161a306d324664dc3a9ea20beff87a74dbb2e6e84218c161a1ce17df60`。
叶函数 harness EXE SHA-256：`dfe0a34d74d50e73ae93a931e955a56939575ad96ef440ab693123475b9bb495`。
间接调用边界只记录目标，不执行 guest callee；不能由此推断整个游戏语义等价。

## 路线 B 的可量化缺口

七个定义包各盘合计 1,287,577 script bytes。3,056 个 native 声明中，203 个具有非零
native index，另 2,853 个 index=0，不能把后者误判为非 native。MC2Game 的 1,651 个
native 声明全部 index=0，后续还需名称注册和宿主实现。

- 26,117 个直接 native-index 调用点全部匹配声明，已验证兼容实现数仍为 **0**。
- 8,375 个 final-object 调用点静态解析为 6,345 个 native 声明、2,030 个脚本声明。
- 13,683 个 virtual、10 个 global、38 个 delegate 调用点共 **13,731** 个动态分派点待处理。
- 字节码验证是递归 token/操作数边界检查，不是 VM、跳转/栈/控制流语义或游戏脚本执行。
- 解析入口严格要求实测大端 446/25、预期定义包存在且 Function 非空；未知 token、游离终止符、
  大小/边界错配均失败，不把操作数字节盲扫成调用。

## 失败记录与原件保护

保留阶段 2 全部失败与阶段 3 初始 vcvars 引号错误、五个 TU 缺标签错误、
ArrayFind token 终止符错误、delegate compare 终止符错误、编码读取错误及 profile fixture 错误。
第一次与最终生成目录、基线与修改态全量构建目录分别保留，没有覆盖失败来制造成功。
两份原始 ISO 均重新 SHA-256 校验，与阶段 1 身份完全相同。

本地证据统一位于 `local/analysis/phase3/`（不提交游戏内容）：

- `module-baseline/`、`module-modified/`：每 TU 命令、输入/对象 hash、日志、退出码。
- `control-flow-baseline.json`、`control-flow-modified.json`：逐函数/逐行 finding。
- `branch-verification-independent.json`：三处分支、五条 goto 和 15 条 PDATA 独立复核。
- `leaf-harness-final/`：真实抽取函数、编译命令、27 行 literal output 与独立期望值。
- `native-gap-disc1.json`、`native-gap-disc2.json`：声明、调用点、原生缺口和逐函数结果。
- `independent-data-verification.json`：两盘第二次解析结果完全相同和 ISO hash 不变。
- `verification/`：源码基线/修改态/隔离回退测试、修改前后 hash、补丁和可执行回退入口。

## 复现与下一道验收门

```powershell
python -m unittest discover -s tests -v
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
```

生成、完整编译和真实叶函数命令见 [分支研究](RESEARCH_BRANCH_FIXES.md)、
[全模块构建实验](EXPERIMENT_MODULE_BUILD.md)；两盘解析命令和固定上游来源见
[UFunction 研究](RESEARCH_UFUNCTION.md)。原始游戏和工具链由执行者按文档本地提供，
公开仓库不包含生成游戏代码、COFF、原版资产、密钥或 SDK。

下一阶段先建立完整宿主链接/运行时初始化与异常语义实验，再逐项补齐 native 注册、
动态分派和脚本 VM；不得将 object 编译成功或 token framing 成功当作可玩 PC 移植。
