# PC 移植与本地化架构草案

状态：设计建议，尚未实现本游戏运行时。查询日期：2026-10-16（Asia/Tokyo）。来源与固定上游 SHA 见 [可行性调查](PORTING_FEASIBILITY.md)。文中的接口、目录和阈值均为拟议契约，不是现存工具或游戏实测结果。

## 1. 双路线边界

```text
本地原版文件（只读，哈希锁定）
        |
        v
版本清单 / 资源目录 / 可追溯技术证据
        |
        +---- A：PPC 分析 -> C++ AOT -> 本机编译 -> 原生运行时适配 -> 原生 EXE
        |
        +---- B：包/脚本/native 依赖图 -> UE3 兼容运行时/逻辑重建 -> PC 原生环境

独立观察基线：原版或资源补丁 -> 固定版本 Xenia/Canary -> 日志/画面对照

localization/<locale>/ -> 占位符/编码/字形/宽度验证 -> 资源补丁或运行时 overlay
```

路线 A 的正常 CPU 执行路径应是离线生成的宿主机器码；仍可能有 GPU、内核及其他兼容行为实现。路线 B 需恢复资源语义、脚本与专用 native 逻辑，在可使用的兼容环境中本机执行。Xenia 观察基线不属于两条原生路线。任何动态 fallback 必须显式披露并统计覆盖范围，不能借“本机 EXE”掩盖对 Xbox 360 CPU 代码的 JIT 或解释执行。

XenonRecomp 只做代码转换，运行时须另行设计；ReXGlue 是完整 SDK 候选；nimauria/Xenon-Recomp 是另一套 module/runtime 体系，不混用其配置文件和 ABI。[XenonRecomp README](https://github.com/hedge-dev/XenonRecomp/blob/ddd128bcca99fe8bfbb99bea583c972351fa6ace/README.md)、[ReXGlue README](https://github.com/rexglue/rexglue-sdk/blob/c94f5ebdcb3c9d1a460ca48e04f9758448f8d518/README.md)、[Xenon-Recomp README](https://github.com/nimauria/Xenon-Recomp/blob/f674eefd9e394a872be6f7f6764fccecde3d1547/README.md)

## 2. 模块与数据所有权

| 拟议模块 | 输入 -> 输出 | 责任 / 禁止耦合 |
|---|---|---|
| source_identity | 显式输入路径 -> 版本及 SHA-256 清单 | 未知版本拒绝修改；不把游戏文件带进 Git |
| resource_inventory | 只读文件 -> 类型/包头/候选编码报告 | 启发式结果保留置信度，不提前定义最终文字格式 |
| package_adapter | 已验证包结构 -> 中性资源视图 / 重建包 | 校验边界、压缩、对齐、引用和二级索引 |
| translation_catalog | 资源视图 + locale -> 稳定 ID / 原文摘要 / 译文 | 文本与控制码分离；不翻译逻辑 ID |
| font_pipeline | 译文字符集 + 开放许可字体 -> 字形/映射/metrics | 不把中文假设写进通用采集器 |
| recomp_backend | 固定工具 SHA + 分析配置 -> 生成 C++ 与诊断 | 不悄悄跳过未支持指令、异常和间接调用 |
| runtime_platform | 生成代码 -> 内核/图形/音频/输入/文件服务 | 通用 Xbox 360 语义归上游，游戏知识归适配层 |
| title_adapter | 源版本 + 已验证 hook -> 本游戏整合 | hook 必须有预期原字节/版本 guard |
| ue3_dependency_model | 包表/对象/脚本 -> native 与资源依赖图 | 区分引擎类、游戏类、脚本和原生实现，不能仅导出美术资源 |
| ue3_compat_runtime | 已验证序列化/脚本/逻辑 -> Windows 本机执行 | 路线 B 独立原型；不假设通用 UDK 等于本游戏运行时 |
| baseline_runner | 固定模拟器 + 配置 -> 日志/截图/场景记录 | 和原生发布物分离命名与验收 |
| release_builder | 验证结果 -> 差分/脚本/清单/校验和 | 不打包完整原版游戏数据；能从干净 checkout 重建 |

## 3. 拟议目录（分阶段创建，不为草案批量建空目录）

```text
config/                  上游锁定、工具配置、版本规则
src/runtime/             本项目通用宿主适配
src/title/               本游戏 hooks 与平台整合
tools/                   身份、提取、导入、字体、验证、打包
localization/<locale>/        结构化翻译、术语、locale 元数据
tests/fixtures/          自制最小包与指令/文本测试，不含原始资产
docs/                    可复核研究、格式与验收记录
build/                   忽略：生成 C++、对象、报告、中间包
dist/                    忽略：本地构建与发布候选
```

原版文件路径通过本地参数指定，工具不依赖开发者机器上的固定盘符。源游戏盘号、区域、补丁版本和资源哈希共同组成 identity；不能只凭文件名 `default.xex` 选择配置。

同轮只读目录证据分别保存在 [游戏结构](RESEARCH_GAME_STRUCTURE.md)、[XEX](RESEARCH_XEX.md)、[UE3](RESEARCH_UE3.md) 和 [双盘布局](RESEARCH_DISC_LAYOUT.md)。目录观察中的 `MC2Game/CookedXenon/*.xxx`、Coalesced 候选应作为解析器输入线索，而不是已验证 PC 可读格式或完整语言支持。

## 4. 资源与字体通路

UE3 cooker 会做平台处理，因此先保留原本 Xbox 360 包语义，不把“另存为 PC 扩展名”当转换。[Epic Content Cooking](https://docs.unrealengine.com/udk/Three/ContentCooking.html)

工程步骤：

1. 清点包、外部 bulk data、纹理缓存、配置/本地化候选及其引用；无证据时不假设存在某个具体文件。
2. 提取时保存包路径、对象路径、属性/索引、原始字节摘要和 locale；稳定 ID 与翻译显示内容分离。
3. 仓库文本可用 UTF-8；运行时编码以原件和解码路径的实际证据决定。
4. 字形链必须同时处理字符映射、字形 atlas、advance/bearing/line height 与 UI 测量，不能只替换贴图。
5. 先尝试增量资源补丁；若字体/布局实证需要运行时改动，再引入已定位 hook。两条原生路线及模拟器对照共用同源语言目录，通过独立输出适配器避免译文分叉。

Epic 的通用本地化机制仅提供调查候选，不证明本游戏使用 `.int` 或公开 UDK 的同一序列化路径。[Epic Localization Reference](https://docs.unrealengine.com/udk/Three/LocalizationReference.html)

## 5. 建议接口契约

以下 JSON 是契约草案，不是支持版本白名单。`null` 表示未知，禁止用它通过版本检查。

```json
{
  "schema_version": 1,
  "title": "MagnaCarta 2",
  "source": {
    "region": null,
    "disc": null,
    "title_id": null,
    "executable_sha256": null,
    "resource_manifest_sha256": null
  },
  "pipeline": {
    "route": "aot",
    "backend": null,
    "upstream_commit": null,
    "toolchain_lock_sha256": null,
    "locale": "zh-CN"
  },
  "validation": {
    "analysis": "not_run",
    "native_boot": "not_run",
    "in_game_localization": "not_run"
  }
}
```

构建必须分开记录 `analysis_passed`、`codegen_passed`、`host_build_passed`、`native_boot_passed` 和 `gameplay_passed`。前一项不能代替后一项，`not_run` 不能自动写成 passed。

## 5.1 路线 B 的独立契约

包模型输出分开保存 name/import/export 表、对象类型、序列化版本、外部 bulk 引用、脚本类/函数及 native 标志。逻辑依赖图的每条边包含来源对象/函数、目标符号或 native 索引、解析置信度及证据位置。游戏资源、脚本数据、游戏 native、系统服务、UE3 运行时与定制引擎代码六层必须分别计数，不以“已导出资源数”代替逻辑覆盖率。

资源转换器按类型输出纹理（含 tiling/mip）、模型/骨骼/动画、材质/shader、地图/流式加载与媒体的验证报告；转换失败保留原始身份与错误，不静默丢对象。兼容运行时加载器必须检查包版本、原生类 schema 和依赖闭包；不支持的 native 绑定明确失败。

当前只有目录和包头观察，不具备构建完整路线 B 的逻辑依赖模型。是否可使用某套 UE3 开发资源或兼容实现、其技术版本与许可是否匹配，均需单独确认；不得导入未经许可的商业 UE3 引擎代码。

## 6. 缺失组件与下一轮实验

| 实验 | 假设 | 最小输入 / 对照 | 通过条件 | 失败后动作 |
|---|---|---|---|---|
| E0 身份识别 | 本地版本可唯一绑定 | 只读 XEX/资源；错哈希对照 | 清单完整；错误版本被拒绝 | 补身份解析，不写补丁 |
| E1 包结构 | 一个候选包可可靠遍历 | 原件与自制截断/越界样本 | 所有边界检查通过，畸形输入非零退出 | 文档记录未知字段/压缩，不猜格式 |
| E2 AOT 分析 | 静态分析覆盖入口所需代码 | ReXGlue 与 XenonRecomp 分别锁 SHA | 输出可重现；未解析项显式列出 | 最小化间接流/异常问题 |
| E3 宿主入口 | 导入与内存模型能推进初始化 | 原版资源，诊断构建 | 固定入口 checkpoint 与无未处理导入 | 按首个失败调用修通用服务 |
| E4 首帧/菜单 | 图形及同步通路可闭环 | AOT 与固定 Xenia 基线 | 可重复首帧/菜单；日志无未知 GPU 命令 | 固定 shader/命令样本排查 |
| E5 中文最小集 | 资源/字体/布局链可回写 | 短句、长句、换行、占位符、缺字对照 | 实际画面正确；错占位符/缺字构建失败 | 修 decoder/metrics，不扩大量翻译 |
| E6 存档/换盘 | 平台服务与内容身份完整 | 新建、保存、退出、重启读档、换盘 | 逐项真实操作通过并留日志 | 最小复现；不把历史 workaround 当修复 |
| B1 对象/依赖 | 包结构可恢复完整依赖 | 一个启动包 + 自制边界错误样本 | 表/偏移/引用校验通过，未知类型明确列出 | 扩充格式研究，不导入 PC 引擎 |
| B2 脚本/native | 脚本层与原生缺口可量化 | 一组类、函数、状态和调用样本 | 输出 native 绑定及调用图，未解析项逐一计数 | 定位 XEX 实现或评估兼容重建工作量 |
| B3 最小 PC 环境 | 兼容实现可执行最小语义 | 可使用的运行时 + 自制对象/脚本 | 本机加载、脚本调用、native 桥接小测试通过 | 重新评估运行时选择，不假设 UDK 兼容 |
| B4 单资源到场景 | cooked 数据可正确转换 | 一个已解析资源，随后最小地图闭包 | 纹理/骨骼/材质/流式引用逐项对照通过 | 保留转换差异，不能称游戏已移植 |

阈值是本项目建议：E0/E1 失败时阻止一切写入；E2 未解决控制流和导入不得宣称可启动；E4 未完成前不以全量译文掩盖运行时问题；正式版本还需战斗、过场、长时运行、多分辨率和完整流程 QA。历史 Xenia 报告包含转场/存档问题，故 E6 不是可省略项。[官方兼容追踪器 #721](https://github.com/xenia-project/game-compatibility/issues/721)

主路线决策点：比较 A 的入口覆盖/运行时缺口与 B 的 native 依赖规模/兼容运行时可用性，并记录人员工作量、可验证最小里程碑和关键未知。A 暂优先做分析实验；若其异常/控制流/GPU 阻断严重而 B 依赖图显示可控缺口，则重新评估 B。二者均不通过时继续补证据，不提前宣布整个项目失败。

## 7. 回归与回滚设计

- 所有写入只面向副本或生成目录；原件修改前后哈希必须一致。
- 资源 round-trip 先要求解析后结构等价；只有实证支持时才要求压缩后逐字节一致。
- 修改后的文本必须通过 protected tokens、编码、字形和固定槽检查；原生运行验收另计，单元测试不构成游戏验收。
- 每次运行记录命令、输入 SHA、工具 commit、配置 SHA、退出码和输出 SHA。
- 回滚通过上一份工具锁定/翻译 revision 重建，并在独立副本复测原版行为；禁止对不匹配哈希文件直接覆盖。
- 分发根许可证不替代依赖审计：XenonRecomp MIT、ReXGlue/Xenia 的三条款 BSD 风格及各依赖归属分别列账；生成代码、字体、翻译和游戏原件分别记录来源。

## 8. 给后续研究者的可复用提示词

```text
读取 AGENTS.md、docs/LOCALIZATION_STANDARD.md、TECHNICAL.md 与本架构。
只完成指定实验 E<N>，先核验源文件身份与上游固定 SHA。
保留原件；不要扩大到全量翻译或未验证运行时补丁。
逐条输出 Verified / High-confidence deduction / Unverified hypothesis。
记录命令、输入哈希、退出码、字面错误、产物哈希与下一最小实验。
分别报告静态检查、宿主编译、原生启动和实际游戏验收；未运行写 not_run。
重要格式写 FILE_FORMATS，失败尝试写 PITFALLS，运行与显示问题写 KNOWN_ISSUES。
```

## 第二阶段落地映射
source_identity 已有只读文件指纹和双盘 XEX 身份/可选头；resource_inventory 已有全部包表与 Coalesced 原文候选。
package_adapter 目前仅实现指定版本的只读表级视图与 Coalesced 内存往返，不声称通用回写或对象语义。
translation_catalog 已有稳定 ID 的本地候选目录/结构对齐，正式 zh-Hans 译文仍为空。
recomp_backend 已启动真实严格 ReXGlue 实验，状态见 EXPERIMENT_ROUTE_A；runtime_platform、title_adapter 与 UE3兼容运行时仍未完成。
模块接口草案不改作虚构实现清单；每项以 PHASE2_RESULTS 中实际命令为准。
