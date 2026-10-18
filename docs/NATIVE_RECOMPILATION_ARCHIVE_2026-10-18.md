# 原生重编译研究技术归档 — 2026-10-18

## 决定与归档身份

Windows x64 原生重编译研发无限期暂停；这是有计划的技术归档，不代表阶段成果无效。近期交付转为原版 Xbox 360 资源简体中文汉化，Xenia 为主要游戏验证环境。归档不继续 ReXGlue SDK、输入并发、内存异常或资源部署修复，不更改 GitHub 仓库 Archived 设置；平台级归档等待另行确认。

- 暂停前已提交源码基线：`ed21d1d`（包含阶段37采集工具，不代表可玩版本）。
- 完整归档标签：`native-research-archive-2026-10-18`，指向本轮归档收尾提交；标签不标识玩家发行版。
- 未完成实验独立分支：`research/input-metadata-watch-2026-10-18`，提交 `ca5c942d993bac629c50aab09063c81bace66fe6`，基于暂停前基线。该分支不合入 `main`，不作为已验证修复。
- 稳定维护状态只提交已完成的研究说明、归档文档及文档回归测试；既有运行行为、SDK、生成游戏代码和部署根不变。

## 工作区盘点与保留

任务开始时有8份未暂存修改、1份已暂存研究说明、1份未跟踪实验源码。原暂存区补丁、工作树补丁、321份源码快照及逐文件SHA256均保存于本地 `local/analysis/archive-20261018/`。未提交状态的原始快照独立于后续稳定基线，未静默丢弃。

| 类别 | 保存位置与状态 |
|---|---|
| 阶段1～29 | `docs/PHASE1_RESULTS.md` 至 `docs/PHASE29_RESULTS.md`，原记录保留 |
| 阶段30～34 | Village、PathNode、Collision、Cinook、Terrain 专项研究，见[状态索引](STATUS.md) |
| 阶段35 | [structures 原包验证及有限部署关联](RESEARCH_STRUCTURES_DEPLOYMENT.md)，完成说明正常提交，原混合失败保留 |
| 阶段36 | [门锁、ABI与实际回退](RESEARCH_INPUT_SERIALIZATION.md)，已验证范围与未决问题分开保留 |
| 阶段37 | [同对象输入异常采集](RESEARCH_INPUT_CONCURRENCY.md)，已有提交与全部本地证据保留 |
| 阶段38未完成实验 | 独立研究分支保存4份实验源改动；`local/analysis/phase38/`保存所有脚本、构建、watch日志、minidump及准备失败，不作为已完成阶段 |
| 本地研究与输入 | `local/analysis/phase1` 至 `phase38`、`phase36-closeout`、`local/upstream`、双盘原ISO、`research/`均盘点；受保护游戏内容不公开 |
| 维护与恢复 | 历史清理报告、`local/maintenance/retired-keepers.json`、保留副本和兼容junction保持有效 |

实验分支中的 `input_metadata_watch.cpp`、`build_input_probe.py --watch` 为未验收的硬件监视尝试；另外两份探针源码只含空白变动，原样保存用于精确追溯。稳定分支恢复任务开始前已提交的诊断源，不新增或继续开发监视器。

完整本地文件清单、大小与SHA256、活动输入复核、测试原文、源码事务、公开提交扫描和清理报告集中于 `local/analysis/archive-20261018/`。这属于本机保留，不构成离盘备份；公开Git仅保留可公开研究源码、文档和指纹，不含本地游戏或SDK。

## 成果分类

| 分类 | 归档结论 |
|---|---|
| 已完成 | 原版双盘扫描、XEX/Coalesced/UE3解析工具、严格生成与197TU构建流程、诊断脚本、失败记录、版本守卫与回退机制 |
| 已验证（限定输入） | 原入口与部分初始化、部分原函数差分、SDK标题/主菜单/部分序章画面读回、有限自动START/A、部分单成员部署回退、输入门锁ABI与有限压力控制；范围见专项记录 |
| 未完成 | 可玩的Windows原生移植、可见呈现及物理输入完整验收、序章/字幕完整结束、首场景/移动/战斗、存档/换盘/通关、阶段38首个破坏写入闭环 |
| 未解决 | SDK刷新并发及生命周期覆盖、负八读取的完整写入来源、早期critical-section AV、`C0000374`堆终止、`C000001D`及资源/运行时剩余缺口 |
| 汉化待验证 | 字体与编码/映射/metrics、控制码保护、文本回写、Xenia未修改对照及修改后游戏内显示；尚无正式中文补丁 |

门锁保持默认关闭，仅覆盖当前host输入导入，不是SDK内部全局修复。exit26是45秒有界观测，不是游戏正常退出；timeout不自动等于死锁；无panic或非黑图像不证明加载完成。失败样本不被后续通过样本覆盖。

## 冻结开发环境与原始输入

历史复现平台为Windows x64；工具测试要求Python 3.12+，本轮使用Python 3.14.2。原生构建固定LLVM/Clang 20.1.8、VS 2022 Build Tools（MSVC 14.44.35207）和Windows SDK 10.0.26100.0，通过 `vcvars64.bat` 加载构建环境，不依赖全局PATH。

ReXGlue SDK 0.10.0，Tom Clay / Xenia contributors，commit `f5337cdc947ff6d4c4196737e2c807a48f2a1fc2`；上游与许可保留于[致谢](../CREDITS.md)及[原生分支调查](RESEARCH_BRANCH_FIXES.md)。SDK二进制和第三方源码仅留本地，不随公开仓库分发。

| 输入 | SHA256 |
|---|---|
| Disc1 ISO，7838695424字节 | `23e96219aa8b2116239c35e6f65013329bfd298d46a726edffa5224498028ac5` |
| Disc2 ISO，7838695424字节 | `9497b336d37529fd8ed1d0d64b560b130354fa1d6168fad1dd428e51e8f6bea2` |
| Disc1原XEX | `26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f` |
| `rexruntime.dll` | `e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a` |
| `clang-cl.exe` | `57e32b1ea2456f12f97bf802453171bbff12d56b2c486b4eca0c75343c0cda2c` |
| 最后保留的完整研究host `module_probe.exe` | `323ad3852a94a2decfef5e5d86e5bf4b03020230b07884d5c2c80a3e0d7e939c` |

完整SDK、生成树、对象、资源根及旧探针的逐文件身份以本地 `phase37/fixed-inputs.json` 和本轮活动输入检查为准。系统头树未逐文件hash，不能承诺跨机器位级相同；源码基线、197对象和最后构建host是不同身份，不混为同一提交产物。

## 最后可复现研究基线

- 生成树：`local/analysis/phase28/strict-codegen/project/generated/default-disc1`，固定 `object-flag-leaf` profile，58172体、58418映射。
- 严格FP对象：`local/analysis/phase28/module-object-flag`，197个TU，保留构建记录、完整输入hash及 `/fp:strict` 合同。
- 完整host：`local/analysis/phase36-closeout/host-build`，保留源码/头快照、编译和链接命令、linker map、输入清单、运行原文；原编译/链接exit0不等于标题整体判定通过。
- 活动资源根：`local/analysis/phase35/root-structures`，只作冻结研究输入，不继续部署下一成员。
- SDK：`local/upstream/rexglue/sdk/win-amd64`；编译器：`local/upstream/llvm/unpacked/bin/clang-cl.exe`。
- 精确历史构建命令：`local/analysis/phase36-closeout/build-command.json`；独立采集工具步骤见[阶段37](RESEARCH_INPUT_CONCURRENCY.md)，完整生成链见[BUILDING.md](../BUILDING.md)。

历史复现顺序为：核对双盘/XEX与上游指纹 → 使用固定profile严格重生 → 全197TU严格编译 → 核验全部对象与host快照 → 显式全量链接 → 按原资源根与配置进行有界运行。输出使用新目录；清理已退休历史副本须先依[维护文档](LOCAL_MAINTENANCE.md)恢复再运行，不以新产物覆盖旧失败。

归档恢复源码可用独立checkout，不覆盖现有工作区：

```powershell
git clone https://github.com/jyh9521/MagnaCarta2-Recompiled.git research-archive
cd research-archive
git checkout --detach native-research-archive-2026-10-18
# 未完成实验只在独立checkout查看，不合入稳定分支：
git show origin/research/input-metadata-watch-2026-10-18 --stat
```

远端克隆查看研究分支时使用 `origin/research/input-metadata-watch-2026-10-18`。干净checkout含公开工具，不含原版输入/私有SDK；本地冻结输入需按上述指纹单独准备。恢复归档不构成重新启动原生研发。

## 后续汉化准备

1. 先固定Xenia具体版本/commit、GPU后端与配置；本地现有 `local/upstream/xenia` 是历史格式研究来源，不作为已验证模拟器安装证明。
2. 使用原版双盘与未修改资源建立Xenia对照，记录启动、视频、字体、菜单与存档行为。
3. 完成最小简体字集、字体来源许可、编码与glyph mapping调查；确定metrics、基线、换行和裁切规则。
4. 构建小样本文本提取—保护token校验—回写—结构校验—Xenia游戏内对照与实际回退，之后再开展批量翻译。
5. 延续现有 `localization/zh-Hans/` schema及稳定ID；通用工具不硬编码中文，原版内容留在ignored目录。

本轮仅建立准备入口，不执行上述新研发。Git提交和分支名称沿用普通描述性英文，不新增PR或改变仓库名称。

## 归档审查与验证记录

公开提交按暂存内容及独立实验分支分别扫描，核对文本编码、文件类型、大小、凭据特征和新增个人主目录路径；同时检查两条既有源码树的受跟踪文件。人工diff核对确认本轮只增加独立研究说明、归档入口及文档测试，不提交原镜像、游戏衍生生成体、完整资源、第三方SDK或本地dump。扫描属于按规则与人工范围审查，不代替第三方组件许可。

归档前盘点70526个本地文件，登记路径、大小与完整SHA256；缓存与本轮归档目录单独管理。两张原ISO完整hash与既有指纹相同，活动7组输入及最后host的222个直接构建输入逐项核验保持一致。测试与保留清单均保存原文，首次文档尚未生成时产生的4个链接失败也保留，冻结状态下重新验证，不追溯抹除失败。

本轮不重新编译或运行完整原生游戏，不继续SDK故障实验；已有可复现构建和失败行为依据固定输入、历史命令及原日志保存。源码基线/修改/隔离回退测试属于工具验证，不构成新游戏运行验收。精确命令、stdin、literal输出、退出码及恢复hash记录在本地 `source-transaction/VERIFICATION.txt`；测试统计、清理回收和恢复记录见[本轮维护记录](LOCAL_MAINTENANCE.md)。远端提交、标签及对应CI结论在最终归档汇报与本地 `git-ci-verification.json` 中逐项记录。
