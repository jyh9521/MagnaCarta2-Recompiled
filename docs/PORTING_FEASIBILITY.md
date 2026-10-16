# 原生 PC 移植可行性调查

查询日期：2026-10-16（Asia/Tokyo）。本文是第一方公开资料调查，不是游戏运行验收；本次未运行游戏、未生成本游戏的重编译代码、未验证菜单或中文显示。

本地文件证据由同轮只读研究另行记录：[游戏结构](RESEARCH_GAME_STRUCTURE.md)、[XEX](RESEARCH_XEX.md)、[UE3](RESEARCH_UE3.md)、[双盘布局](RESEARCH_DISC_LAYOUT.md)。这些报告的静态目录/包头成果与本文的上游能力调查互补，不等同于任一工具已成功加载本游戏。

## 1. 证据规则与当前结论

- **Verified（公开来源）**：能从下列作者仓库、许可证、代码或 Epic 文档直接确认；不等于本项目本机实测。
- **High-confidence deduction**：根据已知组件职责推导的工程判断。
- **Unverified hypothesis**：涉及本游戏具体二进制、资源或运行行为而尚无本地证据。

**High-confidence deduction：两条原生路线均保留，不把模拟器打包称为原生移植。** 路线 A 是静态重编译与运行时适配；路线 B 是 UE3 原生环境重建或逻辑移植。Xenia/Canary 是两条路线之外的观察基线。当前只足以选择实验顺序，不足以宣布任一路线可行或承诺完成日期。

## 2. 上游锁定快照

以下 SHA 直接查询 GitHub REST API 的仓库默认分支和 commit；日期为提交的 committer UTC 时间。`archived=false` 仅表示未归档，不代表仍有持续开发。标签查询结果不等于推荐版本；发布标签与默认分支提交分别记录。

| 项目 / 维护者 | 默认分支与本次 SHA | 提交时间 UTC | 标签 / 发布 | 本次维护观察 |
|---|---|---|---|---|
| [XenonRecomp / hedge-dev](https://github.com/hedge-dev/XenonRecomp) | main / `ddd128bcca99fe8bfbb99bea583c972351fa6ace` | 2025-08-04 13:56:26 | tags API 返回空列表 | 未归档；默认分支近期提交较少，不能据此判定弃坑 |
| [ReXGlue SDK / rexglue，创始作者 Tom Clay](https://github.com/rexglue/rexglue-sdk) | main / `c94f5ebdcb3c9d1a460ca48e04f9758448f8d518` | 2026-08-21 22:11:28 | latest release `v0.10.0`，2026-08-21 22:28:02 UTC；tag commit `f5337cdc947ff6d4c4196737e2c807a48f2a1fc2` | 未归档；README 明示早期开发及破坏性 API 变更 |
| [Xenon-Recomp / nimauria](https://github.com/nimauria/Xenon-Recomp) | main / `f674eefd9e394a872be6f7f6764fccecde3d1547` | 2026-10-10 11:24:54 | tags API 空；latest release API 404 | 未归档；README 指向开发分支，见下文 |
| [Xenia / xenia-project，Ben Vanik 与贡献者](https://github.com/xenia-project/xenia) | master / `95a5c3ee250f80c3b9d139658649d9ffb6db3eec` | 2026-02-18 19:40:20 | tags API 返回空列表 | 未归档；不要把 master 与 Canary 混用 |
| [Xenia Canary / xenia-canary](https://github.com/xenia-canary/xenia-canary) | canary_experimental / `583528e8e3d763a86a37aa848a7f4019e579362a` | 2026-10-16 05:11:16 | latest release `583528e`，2026-10-16 05:35:34 UTC | 未归档；查询日仍有提交与发布 |

快照复核入口（第一方 API）：[XenonRecomp commit](https://api.github.com/repos/hedge-dev/XenonRecomp/commits/main)、[ReXGlue commit](https://api.github.com/repos/rexglue/rexglue-sdk/commits/main)、[ReXGlue release](https://api.github.com/repos/rexglue/rexglue-sdk/releases/latest)、[Xenon-Recomp commit](https://api.github.com/repos/nimauria/Xenon-Recomp/commits/main)、[Xenia commit](https://api.github.com/repos/xenia-project/xenia/commits/master)、[Canary commit](https://api.github.com/repos/xenia-canary/xenia-canary/commits/canary_experimental)、[Canary release](https://api.github.com/repos/xenia-canary/xenia-canary/releases/latest)。这些 API 是动态入口，实施时必须重新查询并固定 SHA。

## 3. 名称、组件与许可证辨析

### 3.1 hedge-dev/XenonRecomp

**Verified（公开来源）**：这是 Xbox 360 PowerPC 到 C++ 的转换工具，README 明确不提供完整运行时。文档列出异常处理、MMIO、跳转表及函数边界分析等限制；生成成功不代表可执行或可玩。架构包括 XenonAnalyse、XenonRecomp、XenonUtils 和测试。当前文档写有 ARM64 的 SIMDe 支持，因此不沿用旧资料“只支持 x86”的结论。[固定版 README](https://github.com/hedge-dev/XenonRecomp/blob/ddd128bcca99fe8bfbb99bea583c972351fa6ace/README.md)

根许可证为 MIT；其使用 Xenia/Canary 研究和代码的归属也须保留，依赖许可证逐项处理。[LICENSE.md](https://github.com/hedge-dev/XenonRecomp/blob/ddd128bcca99fe8bfbb99bea583c972351fa6ace/LICENSE.md)

### 3.2 ReXGlue SDK

**Verified（公开来源）**：这是包含运行时与工具链的另一套 SDK，基于 Xenia，AOT 设计受 XenonRecomp/rexdex 启发，不是仅给 XenonRecomp 改名。README 列有 Windows AMD64、Linux AMD64/ARM64 构建通道，不能据此推断所有游戏在这些平台均可运行。[README](https://github.com/rexglue/rexglue-sdk/blob/c94f5ebdcb3c9d1a460ca48e04f9758448f8d518/README.md)

根 LICENSE 实际是三条款 BSD 风格文本，保留 Tom Clay 及 Xenia 归属。API 的 `NOASSERTION` 不是“没有许可”。[LICENSE](https://github.com/rexglue/rexglue-sdk/blob/c94f5ebdcb3c9d1a460ca48e04f9758448f8d518/LICENSE)

其源码包含 `include/rex/audio/xma/`、kernel/xam/xboxkrnl 等子系统；存在实现不等于本游戏路径已覆盖。[源码树](https://github.com/rexglue/rexglue-sdk/tree/c94f5ebdcb3c9d1a460ca48e04f9758448f8d518/include/rex)

CLI 有 `init`、`codegen`、测试生成和迁移入口；验证失败默认非零退出，实验不使用 `--force` 掩盖失败。[作者 CLI 文档](https://github.com/rexglue/rexglue-sdk/wiki/rexglue-CLI-Commands)

### 3.3 nimauria/Xenon-Recomp 确为不同项目

**Verified（公开来源）**：连字符名称对应独立仓库与作者，架构是共享 Xenon 运行时加各游戏 module；不能与 hedge-dev 项目混称。README 明示尚无确认可玩的商业游戏，首个 Ace Combat 6 集成仍有 GPU/音频停滞；这些是上游自己声明，不是本游戏测试结论。它不应成为“现成通用运行器”的依据。[README](https://github.com/nimauria/Xenon-Recomp/blob/f674eefd9e394a872be6f7f6764fccecde3d1547/README.md)

README 的开发分支 `development-restructure` 本次查得 `4f42f48086fc81bfd28c6f097cb8af9c9f4035ec`，2026-10-14 14:40:40 UTC。评估默认分支与开发分支须分别锁定，不能混合结论。[开发分支 commit](https://api.github.com/repos/nimauria/Xenon-Recomp/commits/development-restructure)

根许可证 MIT；项目另有第三方声明，根许可证不能覆盖全部依赖。[LICENSE](https://github.com/nimauria/Xenon-Recomp/blob/f674eefd9e394a872be6f7f6764fccecde3d1547/LICENSE)、[第三方声明](https://github.com/nimauria/Xenon-Recomp/blob/f674eefd9e394a872be6f7f6764fccecde3d1547/THIRD_PARTY_NOTICES.md)

### 3.4 Xenia 与 Canary

**Verified（公开来源）**：二者是模拟器研究项目。Canary 是包含 master 以外变更、更新更频繁的分支生态；官方 quickstart 说明硬件/API 要求并不保证游戏表现。它们适合作为比较运行时，不能作为原生 AOT 的交付标签。[Xenia README](https://github.com/xenia-project/xenia/blob/95a5c3ee250f80c3b9d139658649d9ffb6db3eec/README.md)、[Canary Quickstart](https://github.com/xenia-canary/xenia-canary/wiki/Quickstart)

两者根 LICENSE 均为三条款 BSD 风格；实际分发还要审计依赖。[Xenia LICENSE](https://github.com/xenia-project/xenia/blob/95a5c3ee250f80c3b9d139658649d9ffb6db3eec/LICENSE)、[Canary LICENSE](https://github.com/xenia-canary/xenia-canary/blob/583528e8e3d763a86a37aa848a7f4019e579362a/LICENSE)

## 4. UE3 Xbox 360 与 Windows：已知与未知

**Verified（Epic 通用文档）**：UE3 的 cooker 可剥离编辑器数据、交换字节序、转换资源为平台原生格式和生成 seek-free 包。PC 可读 cooked/uncooked 的文档陈述，不意味着任意 PC 程序可以直接读任意 Xbox 360 商业游戏的 cooked 包。控制台 `.xxx`、纹理缓存和启动/原生脚本包具有关联。[Epic Content Cooking](https://docs.unrealengine.com/udk/Three/ContentCooking.html)

**Verified（Epic 通用文档）**：UE3 有 INT 等本地化文件及本地化对象机制，但零售游戏可以自定义或合并其数据。[Epic Localization Reference](https://docs.unrealengine.com/udk/Three/LocalizationReference.html)

**High-confidence deduction**：CPU 转换之外仍需解决 Xenos GPU/着色器、内核服务、线程/同步、文件/存档、音频和输入。换成 Windows 编译器不会自动把这些调用转换为 Windows UE3。通用 UDK 也不是本游戏的源代码或重建环境。

**Verified（第一方工具源码）**：UEViewer 作者仓库 `gildor2/UEViewer` 在 `a0bfb468d42be831b126632fd8a0ae6b3614f981` 中按低 16 位解析 FileVersion、高 16 位解析 LicenseeVersion，并把 `446/25` 识别为 Magna Carta 2。它是该工具的实现证据，不是 Epic 对本游戏的官方格式说明。[UnPackage.cpp](https://github.com/gildor2/UEViewer/blob/a0bfb468d42be831b126632fd8a0ae6b3614f981/Unreal/UnrealPackage/UnPackage.cpp)、[GameDatabase.cpp](https://github.com/gildor2/UEViewer/blob/a0bfb468d42be831b126632fd8a0ae6b3614f981/Unreal/GameDatabase.cpp)

**High-confidence deduction（本游戏包头）**：本轮目录/包头研究提供的样本 `9e2a83c1 001901be`，按大端字段得到 `0x001901BE`，与 `446/25` 相符；该匹配不证明全部包同版、完整对象反序列化、重建或 PC 加载成功。

**Unverified hypothesis（本游戏）**：自定义原生类与脚本绑定、包压缩、文字实际来自 coalesced/对象属性/独立表中的哪一部分、字体是纹理还是其他中间件、视频和音频具体编码。目录中的 Coalesced 和 CookedXenon 候选不证明其内容已解析，仍须逐项验证。

## 5. 本游戏现有公开兼容证据

**Verified（公开报告存在）**：Xenia 官方兼容追踪器的 [#721 / 4E4D080B - MagnaCarta2](https://github.com/xenia-project/game-compatibility/issues/721) 当前标签含 `state-gameplay`、`gpu-drawing-corrupt`、`tech-engine-unreal`。初始报告是 2017 年，评论记录了读档、Abazet 转场崩溃和换盘问题；这些是历史特定版本报告，不是 2026 年构建的验收结果。此 Title ID 仅作待匹配线索，不能替代本地 XEX 身份验证。

本次 Canary 官方兼容仓库的 `Magna` 搜索未返回条目，不能推导“没有问题”或“已经修复”。查询范围有限，后续应以实际构建日志和固定场景复测。

## 6. 路线 B：UE3 原生环境重建或逻辑移植

### 6.1 六层边界

必须分开调查：数据资源、UnrealScript、游戏专用原生代码、Xbox 360 系统依赖、UE3 运行时、游戏特定引擎修改。包文件可被浏览不代表脚本能运行；脚本可被解析不代表其 native 函数存在。Epic 的 cooker 文档明确区分原生脚本包、地图、启动包、外部纹理与资源转换，支持这种依赖分层，但不能证明本游戏的具体依赖清单。[Epic Content Cooking](https://docs.unrealengine.com/udk/Three/ContentCooking.html)

### 6.2 当前证据与缺口

| 研究项 | 当前证据 | 尚待核验 / 最小实验 |
|---|---|---|
| 构建与定制 | 包头候选与 UEViewer 的 446/25 分支匹配（高置信） | 不能由该版本号恢复实际引擎源码；先遍历所有包头与差异 |
| 字节序/序列化 | 本轮样本为大端头；Epic 明示平台 cooking 会换序 | 逐类解析 name/import/export/property/bulk data；禁止全文件盲目换序 |
| 纹理/压缩 | 仅包候选和平台路径，不是已解码图像 | 确定每种格式、mip、tiling、压缩块与外部引用；单纹理解码并对照 |
| 模型/动画/骨骼 | 未解析对象载荷 | 骨骼层级、顶点布局、压缩动画、坐标和蒙皮逐项验证 |
| 材质/着色器 | AOT CPU 转换不解决材质运行时 | 取单一材质依赖闭包，验证参数语义与 PC shader 路径 |
| 地图/流式加载 | 双盘目录与共有/独有成员可作为资源图起点 | 导入导出、关卡对象、碰撞、流式关卡/外部 bulk 引用未解析 |
| UnrealScript | 尚未确认脚本类/函数及 bytecode 范围 | 枚举类/函数/状态与指令版本，不把包内可读字符串当脚本 |
| native 绑定 | 未建立 native 索引、原生类或 XEX 调用图 | 输出脚本到 native 的绑定图、关键 API 与缺失实现规模 |
| UI/字体/本地化 | 有 Coalesced 候选，不等于结构/显示已验证 | 先解析一个显示文本及其字体/布局依赖，不预设 UI 中间件 |
| PC 运行环境 | 没有验证兼容的本游戏 Windows 运行时 | 先明确可使用的开发资源或兼容实现及许可，再加载自制最小对象 |

**High-confidence deduction：现有资源和脚本证据不足以证明能重建游戏逻辑。** 目前尚无脚本覆盖率、native 绑定数量或专用引擎修改规模，不能说“资源已提取就只剩导入 UDK”。路线 B 的主要阻断点是兼容运行时和原生逻辑缺口，且可能同时面对所有资源类型的转换；这不是通过更换扩展名或引擎版本能够消除的工作。

## 7. 双路线证据矩阵

| 问题 | A：AOT 原生移植 | B：UE3 重建 / 逻辑移植 | 本游戏状态 / 下一项证据 |
|---|---|---|---|
| CPU/游戏逻辑 | 分析 PPC，保留原生逻辑并 AOT | 脚本解释/执行加专用 native 逻辑重建 | 未测试；函数/间接调用与 native 绑定图 |
| GPU/着色器/纹理 | Xenos 共享运行时或专用桥接 | 转换 cooked 资源与材质，构建 PC 渲染路径 | 未测试；固定场景截图和 shader 日志 |
| 内核/XAM/同步 | 保留 Xbox 调用并适配语义 | 重建平台层，替换依赖并验证时序 | 未测试；导入表和首个失败调用 |
| 音频/视频 | 解码并桥接原版调用 | 转换媒体与事件/动画绑定 | 未测试；首段音画同步 |
| 文件/存档/双盘 | 虚拟盘路径与原布局适配 | 新加载器/保存逻辑需兼容或明示迁移 | 未测试；存/读/重启/换盘闭环 |
| 中文/字体 | 资源或 runtime overlay | 本地化加载器与原生 UI/字体整合 | 未测试；单界面短句与宽度/缺字验证 |
| 完成标准 | 本机 AOT 产物，完整玩法验收 | 本机 UE3 兼容运行时，逻辑与资源完整验收 | 当前均未达到；Xenia 仅用作外部对照 |

## 8. 候选顺序与阻断条件

**工程建议（不是兼容性结论）**：当前暂以路线 A 的小规模 ReXGlue / XenonRecomp 比较作为优先实验，因为可研究的公开 AOT 组件已存在；这不是宣布 A 绝对正确。路线 B 同时开展包/脚本/native 依赖勘测，待缺口可量化后再重审主路线。nimauria/Xenon-Recomp 留为观察候选，不在首轮绑定其未稳定模块 API。Xenia master 与 Canary 均保留固定版本观察基线。

同轮已完成的底层证据见上述本地研究报告；目录、哈希和包头观察不能代替可执行内容分析。尚缺完整原生导入覆盖表、间接控制流清单、可复现 AOT 构建锁定、渲染/媒体路径、存档/换盘适配、脚本/native 依赖图、路线 B 兼容运行时原型、字体/编码回写 POC 与实际游戏验收记录。

下一轮按最小失败面推进：

1. 只读采集本地 XEX/资源 SHA-256、大小、区域/Title ID/版本；原始文件留在忽略目录。
2. 先做包头/目录清单和文字候选扫描；每条发现标状态与来源偏移。
3. 对每个候选仅执行分析/生成，记录工具 SHA、命令、退出码、未解析控制流、导入和异常警告；生成不等于启动。
4. 首个 AOT 宿主仅目标“到入口并输出诊断”；随后依序推进画面、菜单、首场景、存读档、换盘，不跳级承诺。
5. 另建模拟器原版基线，记录硬件、构建、后端、配置哈希、日志和场景截图，再做同场景中文 POC 对照。
6. 若关键异常/同步/GPU 通路缺失，停止扩大转换或全量翻译，形成可提交上游的最小复现；下一步转为修通用组件，而不是静默 stub 返回成功。
7. 路线 B 首先输出单个启动包/地图的依赖闭包、脚本 native 调用图和缺失实现清单；仅当具备可使用的 PC 兼容运行时且一个自制对象可加载后，才尝试一个已解析真实资源的离线显示。单资源显示不算游戏逻辑执行。

## 9. 调查复核命令

以下是复核用 PowerShell 模板，不代表已在本机编译上游；API 快照查询本次已执行：

```powershell
$repo = 'rexglue/rexglue-sdk'
$metadata = Invoke-RestMethod "https://api.github.com/repos/$repo"
$commit = Invoke-RestMethod "https://api.github.com/repos/$repo/commits/$($metadata.default_branch)"
$commit | Select-Object sha, @{n='committer_utc';e={$_.commit.committer.date}}
Invoke-RestMethod "https://api.github.com/repos/$repo/releases/latest" |
  Select-Object tag_name, published_at, html_url
```

本阶段仅记录研究和架构方案；尚未复用或引入上述第三方代码。上游许可证、作者、固定 SHA 和采用组件须在实际引入时同步登记到 LICENSING.md。
