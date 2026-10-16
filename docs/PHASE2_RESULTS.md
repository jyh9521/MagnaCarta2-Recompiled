# 第二阶段验收：身份、文本、包引用与两路线实验

日期：2026-10-16（Asia/Tokyo）。环境：Windows x64、Python 3.14.2；本地 Git 基线 458a2b6。
本报告区分真实原版静态证据、宿主工具执行、代码生成、编译对象与游戏运行。

## 已完成与实际状态

|工作|实际结果|状态|
|---|---|---|
|双盘 XEX 身份|Title ID 均 0x4E4D0811；Media ID 4C23BE53 / 4D4C6B53；盘号 1/2、2/2|PASS（元数据，非签名认证）|
|可选头/导入库|每盘 17 头边界/重叠校验，basic 压缩表，xam 182 / xboxkrnl 323 条记录地址|PASS（不等于唯一 API 数）|
|Coalesced|8 个容器解析→内存序列化，逐字节与 SHA-256 一致|PASS|
|原文候选与对照|每盘 35901 条；16971 组结构配对；正式译文 0 条|PASS（候选结构，非人工语言审核）|
|UE3 表/引用|盘 1 为 1912、盘 2 为 2233 包，全部 tables-validated，0 errors；含 LZX|PASS（表级，不含对象语义）|
|两盘引用文件候选|本盘 7339 / 8710 条；盘 1 有 5 条仅另一盘唯一 stem 候选|PASS（不等于动态加载闭包）|
|A：真实 XEX 载入|固定 ReXGlue v0.10.0 init 实测成功|PASS|
|A：第一轮严格分析|2 UnresolvedCall，exit=1，保留失败日志|FAIL（未掩盖）|
|A：第二轮入口 hint|2 个入口假设；严格 codegen exit=0，397 个文件；仍有 3 处条件分支生成为 REX_FATAL|PASS（生成阶段；语义未验证）|
|A：编译最小实验|真实生成 mc2_probe_recomp.122.cpp，用官方 Clang 20.1.8 编译为 COFF 对象，exit=0|PASS（仅该 TU）|
|B：宿主解析/解压|MSVC 实际构建 libmspack 桥接 DLL，宿主执行并验证全部包表|PASS（非游戏运行时）|
|B：native flags/index/字节码、兼容运行时|未实现，不把 12901 Function 等同 native 缺口|NOT TESTED|
|完整生成模块编译/链接、游戏逻辑/首帧/可玩性|未完成|NOT TESTED|
|中文字体/排版、资源部署回写、保存/换盘/通关|未完成|NOT TESTED|

最重要的纠正：Coalesced.int 实际包含大量韩文；大端长度/包整数下存在 UTF-16LE 载荷，不能按后缀或整包字节序猜测。
原版两张 ISO 再次全量 SHA-256 与第一阶段相同。工具输出只在 local，未向镜像写入；未上传密钥、商业资源、SDK、生成的游戏 C++ 或对象文件。

## 可复现入口

```powershell
python -m unittest discover -s tests -v
python tools/formats/build_lzx.py --workspace local/analysis/phase2
python tools/formats/ue3.py 'MagnaCarta II (Korea) (Disc 1).iso' local/analysis/phase1/disc1.json --output local/analysis/phase2/ue3-disc1.json --lzx-library local/analysis/phase2/ue3_lzx.dll
python -m tools.research.probe_coalesced --manifest local/analysis/phase1/disc1.json --image-root . --output-dir local/analysis/phase2/coalesced/disc1
python -m tools.research.compare_dependencies local/analysis/phase2/ue3-disc1.json local/analysis/phase2/ue3-disc2.json --output local/analysis/phase2/cross-disc-dependencies.json
python scripts/verify_stage.py --baseline-dir local/analysis/phase2/baseline --baseline-manifest local/analysis/phase2/baseline_manifest.json --output-dir local/analysis/phase2/verification
```

盘 2 命令替换输入/清单/输出盘号；第一阶段清单可用自备原版镜像重新生成，不依赖随仓库分发的商业数据。
最后一条需要修改前真实源码快照，不能把它当干净 checkout 的游戏构建步骤。源快照仅用于本轮回退验证。

## 自动验证与证据位置

修改前基线：43 tests / OK / exit=0。修改后 146 tests / OK / exit=0；隔离回退后 43 tests / OK / exit=0。确切输出保存在本地 `verification/VERIFICATION.txt`。
隔离回退按修改态和基线逐文件 SHA 守卫，原模板/源码恢复、新增源码移除；主工作树及 MODIFIED_FILE 保留修改态。
独立自制样本审查发现并修复输出硬链接污染、清单身份/范围和 summary 表重叠，新增回归；没有以原版资源充当公开测试夹具。

本地证据均在 `local/analysis/phase2/`：
- real-verification.json：双盘真实命令、退出码、输出，以及最终整盘哈希。
- xex-disc1.json / xex-disc2.json：不含密钥/签名载荷的身份与可选头。
- coalesced/discN/：完整本地文本报告、未翻译候选及配对。
- ue3-discN.json / ue3-summary.json / cross-disc-dependencies.json：包身份、表计数及候选图。
- 路线 A 代码生成、编译日志与产物身份详见独立实验文档；完整源码和对象只存本地。
- verification/：MODIFIED_FILE.py、DIFF_FILE.patch、VERIFICATION.txt、可执行 ROLLBACK.sh，以及源码快照/隔离副本。

## 后续最高优先级

路线 A 先修复已定位的 3 处 REX_FATAL 条件分支及验证入口假设，推进整个生成模块的正确工具链编译和导入语义；单 TU 编译成功不是可运行 EXE；这 3 处 REX_FATAL 在对应路径会中止，尚未实际触发执行。
路线 B 从 MC2Game/Core 的一个 UFunction 载荷恢复 flags/native index/字节码，量化游戏专用逻辑缺口。
本地化先确认实际加载分支、控制码、未确定窄串编码与字体依赖，再做受版本保护的单文本中文 PoC。

[XEX 详报](RESEARCH_XEX.md) · [Coalesced 详报](RESEARCH_COALESCED.md) · [UE3 详报](RESEARCH_UE3.md) · [路线 A](EXPERIMENT_ROUTE_A.md) · [路线 B](EXPERIMENT_ROUTE_B.md)
