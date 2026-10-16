# MagnaCarta 2 CN

Xbox 360《MagnaCarta 2》原生 Windows x64 移植研究与简体中文本地化工程。
目标是用户自备原版数据 + 本项目工具/兼容运行时；不是 Xenia 启动器。

## 当前状态（2026-10-17，第九阶段）
- 已实现：只读清单、双盘 XEX 身份/可选头、Coalesced 原文候选与字节往返、UE3 446/25 包表/引用图、基础校验。
- 可选 LZX 依赖：固定 libmspack 源码构建；两盘全部 4145 个 UE3 候选已通过表级解析。
- 已勘测：用户提供的两张 ISO，详见 `docs/RESEARCH_GAME_STRUCTURE.md`。
- 已修复三处 REX_FATAL 条件分支及五组 SEH 边界；真实生成模块 **197/197 TU 全量 Clang 编译通过**，两叶函数 27 组合成输入与独立 PPC oracle 一致。
- 已解析七定义包 **12901 UFunction** 的 native index/flags 与字节码 framing，量化 3056 项 native 声明；未恢复兼容 native 实现。
- 全部 197 对象已显式链接为 Windows x64 宿主；SDK 初始化、58,408 项函数映射复核、内存分配读写释放与关闭通过。
- 已解析 312 个原生名称表、2,676 项非零实现配对及 299 个注册函数模板；203 个有 index 声明均交叉匹配。
- 已执行两个原注册函数、真实 `Object.Add_IntInt` 与真实四字节操作数解码器，8 组输入通过；阶段四的静态数据夹具现已由原像装载替代。
- 原 XEX 已通过官方 SDK 装载，20,119,552 bytes 严格比较仅有 13 个正常变量导入槽变化；已移除 vtable/GNatives 输入夹具。
- 正式 kernel/audio/input 与真实 GPU 插件配置后，实际执行原入口、CRT 链和 main 路径；原 `0x8234FF10` 缺口已由入口元数据严格重生解决，197TU重新编译/链接通过，原回调5组差分通过。
- 823C2740虚分派thunk已严格重生，4组分派差分通过；当前58,411映射、58,165生成函数。完整比较回调 `0x82C1C1A0` 已恢复并通过14组双返回差分；19原成员运行根推进至 `GNatives[0x52] -> 0x82509380` 缺登记，SDK原fatal保留。实际结果见 `docs/PHASE8_RESULTS.md`；这不是玩家可用版本，headless GPU 命令执行不等于可见首帧验收。
- 未实现：本游戏可用的 Windows 原生运行时、游戏资源部署回写、中文字体与正式译文。
- 当前没有玩家安装包；仅标题初始化路径已实测，可玩性、可见首帧、分辨率与帧率支持均为 NOT TESTED。

## 工具入口
基础工具要求 Python 3.12+（当前验证为 3.14.2），使用标准库；完整 LZX 包表解析需要可选本地解码库，构建见 BUILDING.md。
```powershell
python -m unittest discover -s tests -v
python tools/inventory/scan.py local/disc1 --disc disc1 --output local/analysis/disc1.json
python tools/inventory/scan.py local/disc1.iso --disc disc1 --xdvdfs --output local/analysis/disc1.json
python tools/inventory/compare.py local/analysis/disc1.json local/analysis/disc2.json --output local/analysis/comparison.json
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
```
输出应放在输入目录之外；根目录 ISO 可直接显式传入，不需要复制或移动镜像。

## 工程结构
- `tools/inventory/`：语言无关的扫描与比较工具。
- `tools/validators/`：语言无关的数据校验。
- `localization/source/`：本地提取源文，默认忽略；`zh-Hans/`：简体中文工作记录；`review/`：审核流程。
- `locales/zh-CN/`：原模板保留目录，不存第二份翻译；数据主目录为 `localization/zh-Hans/`。
- `docs/`：原版勘测、双路线评估、构建与测试；`local/`：不提交的输入与证据。
- `src/host/`：SDK 初始化、真实 XEX 装载、native 实验和有界标题诊断，不含游戏生成代码或完整兼容引擎。

## 开发入口
[构建](BUILDING.md) · [翻译](TRANSLATING.md) · [技术记录](TECHNICAL.md) · [许可边界](LICENSING.md)
[Coalesced](docs/RESEARCH_COALESCED.md) · [阶段二](docs/PHASE2_RESULTS.md) · [阶段三](docs/PHASE3_RESULTS.md) · [阶段四](docs/PHASE4_RESULTS.md) · [阶段五](docs/PHASE5_RESULTS.md) · [可行性](docs/PORTING_FEASIBILITY.md) · [架构](docs/PORTING_ARCHITECTURE.md) · [下一步](docs/NEXT_STEPS.md)
[仓库](https://github.com/jyh9521/Magna-Carta-2-CN) · [问题反馈](https://github.com/jyh9521/Magna-Carta-2-CN/issues)

## 贡献与发布
提交只包含自编工具、文档和经授权的数据；原版资源不进入仓库。
原始模板改写前已在本地证据目录保留逐文件哈希和副本。
后续发布将验证用户原版版本，构建可复现的补丁，不分发完整商业游戏。
