# 间接回调发现缺口：地址构造、入口与多 return

日期：2026-10-17。本文只报告固定原映像、固定上游源码和已有生成树的只读研究；不自动生成 hint、不改变游戏/SDK/生成源，也不把静态候选宣称为已执行路径。

## 输入与证据层次

- 原 XEX SHA-256：`26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f`。
- 既有独立展开映像：20,119,552 bytes，SHA-256 `d18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9`。研究工具只接受这一完整映像 hash，结果只输出地址、状态和范围散列，不输出原映像内容或密钥。
- 上游源码归属：Tom Clay / ReXGlue SDK v0.10.0 tag commit `f5337cdc947ff6d4c4196737e2c807a48f2a1fc2`；既有本地下载源码及官方 SDK 头，不访问网络/升级工具链。
- 下述 `.cpp` 是固定 tag 对照源码，头文件来自本地官方 SDK 包；源码机制与实际生成结果分别核验，**没有声称已从发行 EXE 反编译证实逐字节相同实现**。原 SDK EXE SHA 与既有 [路线 A 实验](EXPERIMENT_ROUTE_A.md) 相同。

本次重开文件的 SHA-256：

|文件|SHA-256|
|---|---|
|`local\upstream\rexglue\analyze.cpp`|`9818c473b7ab34d03f4ae96480b97648a6d6d4e3ab8ddf6ed69082065bea3c06`|
|`local\upstream\rexglue\phase_gapfill.cpp`|`878a120c08c772e005f92ec44ed5121c65b5b5764c4725896dfe2d7d5e7d20e3`|
|`local\upstream\rexglue\phase_register.cpp`|`84ef12f4746e32cbead96e8fc3d192e2f24f891d11aa4585b5317f7aa0770775`|
|`local\upstream\rexglue\phase_merge.cpp`|`34b4346cef23c386dfc87087f83ae0a192a6fa6e2dc239d8626d59cdcf7e5390`|
|`local\upstream\rexglue\sdk\win-amd64\include\rex\codegen\function_scanner.h`|`2a7108eca3ec9c548a732c013e99c6371d17a86b71d17d730c9e2e7ed12f8d9b`|
|`local\upstream\rexglue\sdk\win-amd64\include\rex\codegen\vtable_scanner.h`|`2f1c75fa17b07060e0b03f62f7de0ae1119524199c2aaaaea69d6b722a647735`|

## Verified：为什么直接调用分析不能代替回调入口发现

固定 `analyze.cpp:57-59` 明确留下 `functionPointerScan(ctx)` 注释：原本用于发现加载代码地址的 `lis/addi` 对，因过多假阳性而禁用。因此不能假设任意代码地址常量构造都会自动变成可登记入口。

`phase_register.cpp` 的输入渠道包括 imports、helpers、显式 CONFIG 和 PDATA。`function_scanner.h` 描述从入口递归发现 reachable blocks、收集直接 `bl` external_calls 与 tail_calls；这不等价于穷举函数指针常量。`vtable_scanner.h:55-75` 则是 RTTI/COL 驱动：先 Complete Object Locator，再表，再可执行 slots，并非“只要任何数据字等于代码地址就登记”。

由完整原映像独立扫描得到：

|目标入口|包含它的 PDATA|直接 B/BL 目标字|对齐 literal 地址字|已验证原函数范围|
|---|---:|---:|---:|---|
|8234FF10|0|0|0|+0x30，hash `5c43c892cc33dcb8b15d083257e0a8211788bb01aaa0698cd379c2164e77665e`|
|823C2740|0|0|3|+0x10，hash `0a315417a24fefd102c136c2b181f682cfa3b65422c9cbdaa146fd6caf719265`|
|82C1C1A0|0|0|0|+0x88，hash `60e3229fb7c29acb4ca50ea10e03bf77af7d9e361a9882d12b2f8e7e9ad3388f`|

`8234FF10` 的 `lis/addi` 构造由 `82D6C814/82D6C834` 组成，经 r9 传到 `823A6150`，不是一条直接 bl 到目标入口；既有原指令与执行缺口证据见 [回调研究](RESEARCH_CALLBACK_ENTRY.md)。`823C2740` 虽有三个静态字引用，也仍曾漏登记，说明“有代码指针字”不足以保证 RTTI 扫描恢复入口；具体 COL 验证失败原因尚未在本地现存源码/运行 trace 中定位，不将其猜成已证事实。虚 thunk 的真实指令和执行结果沿用对应既有阶段实验。

**High-confidence deduction：** 缺少 PDATA/直接控制流边，加上 lis/addi 扫描关闭，解释了这些间接目标不受完整入口发现保证；不是“SDK 已能自动发现全部回调，但注册代码偶然丢一行”。不过本次没有各地址在 Scan/Discover/GapFill 的逐阶段内部 trace，不能断言每个缺口被哪一个 `skip` 分支精确吞掉。

## Verified：82C1C1A0 的两个 return 与内部 C214

原函数范围内 `82C1C210` 与 `82C1C224` 均为 `blr`；非相等路径在 `82C1C208` 条件跳至 `82C1C214`，后者是依赖前段 r8/r11 的内部尾块，不是本次 r6 地址构造的入口。

固定 `phase_gapfill.cpp:39-81` 将 region 逐条扫描，在 `decoded.is_return()` 或指向已知 callable 的尾调用处切段；`segmentStart` 随终止指令后移。`phase_gapfill.cpp:140-151` 跳过已有入口/位于别的函数内的段首；`184-207` 删除被更高 authority 或较早 GAP_FILL 函数吸收的 gap 节点。这套线性补洞/cleanup 不是完整的语义函数边界证明。

**High-confidence deduction：** `C210 blr` 后段恰从 `C214` 开始，与旧树只登记 `C214` 的观测吻合；首个 return 与函数末尾 return 不等价，不能以内部 mapping 存在证明完整 `C1A0` 可执行。旧树前段为何没有留下入口的确切 pass-level 原因仍未验证。

独立比较已完成：旧阶段 7 与新阶段 8 均有 **58,164** 个真实函数体；共同 **58,163** 个 body SHA 全相同；只新增 `sub_82C1C1A0`，只移除 `sub_82C1C214`，mapping 集合也仅此增减，没有共同 mapping 改名。此结果来自严格生成后的只读比较，不是手删 C214，也不证明 C214 从来没有独立外部调用者；目前只能说本次 r6 参数明确指向 C1A0，完整新函数包含该内部块。

## 有界恢复 8286FD30 的 r6 比较回调参数

`tools/research/audit_callback_sites.py` 使用标准库，在原 PE 可执行 section 中找直接 `bl 8286FD30`；对每个 call 最多回看 16 条指令，要求最近 r6 定义是 `addi r6,rS,low`，最近 rS 定义是 `lis rS,high`。中间只有已知无害 GPR effect 模板才继续；未知指令、控制转移、相关寄存器覆盖、同 section 可解码的直接分支进入定义链内部一律记 unresolved。工具不生成 hint，也不按候选参数值重建函数。

固定映像检出 **17 个调用 site、15 个不同候选目标**；17 个局部地址定义链都通过上述有界检查。旧树中只有 `82C1C1A0` 的那一个 site 目标未登记，新树中此目标已登记，其余不变。

|直接 call site|r6 静态候选|旧阶段 7 mapping|新阶段 8 mapping|
|---|---|---|---|
|`82372674`|`82372738`|有|有|
|`824DAF78`|`824DD020`|有|有|
|`8275BF30`|`8275BD78`|有|有|
|`829777FC`|`829754F0`|有|有|
|`829C8E3C`|`829754F0`|有|有|
|`82AB5550`|`82AB5438`|有|有|
|`82BE9A8C`|`82BE50B8`|有|有|
|`82C07A18`|`82C042D0`|有|有|
|`82C0857C`|`82C042C0`|有|有|
|`82C085D4`|`82C042C0`|有|有|
|`82C0B974`|`82C04388`|有|有|
|`82C0D2C8`|`82C0BFF0`|有|有|
|`82C30284`|`82C1E360`|有|有|
|`82C31B14`|`82C1D4C8`|有|有|
|`82C3548C`|`82C1C1A0`|无|有|
|`82C65020`|`82C3DF70`|有|有|
|`82C87D38`|`82C6B9A8`|有|有|

**原范围验证层级：** 每条记录的 `lis`、`addi`、`call`、`range_size/range_sha256` 只认证调用者的地址构造链，**不是回调函数体大小/hash**。完整映像 hash 固定了字节来源；目标落点、mapping 只是静态证据。除本阶段另行完整验证的 C1A0，以及已有 8234FF10/823C2740 专项实验，不在本报告给其他 14 个候选的语义函数范围背书。已映射也不代表执行过或恢复正确。

实际运行证据仅沿用阶段 7 已保存的 failure：`8286FE88 bctrl`、LR `8286FE8C`、CTR `82C1C1A0`，目标本体尚未执行就因 mapping 缺失而失败。该证据证明那次间接调用请求，不证明 17 个构造 site 都实际执行，也不单凭相同 target 将 `82C3548C` 静态构造链与该次执行完整串成已跟踪数据流。原比较语义、夹具执行和修复后启动进展由其他专项实验独立维护。

## 复现、失败边界与证据

```powershell
python -m tools.research.audit_callback_sites --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --generated local/analysis/phase8/compare-codegen/project/generated/default-disc1 --output local/analysis/discovery-reproduction/callback-sites.json
python -m unittest discover -s tests -p test_callback_sites.py -v
```

主复现输入为用户提供的原版 XEX，不依赖旧 phase3 的私有映像文件。原 XEX 从用户 ISO 只读提取的完整命令及固定 SHA 见 [路线 A](EXPERIMENT_ROUTE_A.md)；固定 Xenia 源码的本地准备方式沿用 [原映像实验](EXPERIMENT_XEX_IMAGE.md)。`--xex` 与 `--loader-source` 路径复用已有 hash-locked `image_from_xex()`，只在内存展开并再次核对完整映像 SHA，不输出映像或密钥；该真实输入路径需 `cryptography`，合成测试仅需标准库。`--image` 仍可供已有原映像研究复用，与 `--xex` 互斥。生成树参数只用于对照 mapping，省略 `--generated` 仍可从原 XEX 独立恢复候选；生成树可从既有严格重生流程重建，不要求复制私有生成源。公开仓库只提交研究工具、合成测试和本文。

18 项自制标准库测试覆盖高/低半字有符号组合、目标参数、相对/绝对 branch、无 link/无关 call 排除、r6/source 覆盖、未知 opcode、调用破坏、窗口上限、越界对齐、入链分支与错误映像 hash、两种 CLI 输入合同及互斥/缺参拒绝；全部 `OK / exit=0`。拒绝案例是预期 fail-closed，不是据错误输入继续猜候选。

本地 `local/analysis/phase8/discovery-*` 保存：旧/新 r6 site JSON、三已知目标的 PDATA/地址引用/return 见证、源码 hash、独立生成树 diff、测试逐字日志。本研究未修改 hint、生成树或 SDK；未对候选自动登记/自动执行。尚未恢复的边界与运行时闭包继续保留为未知。


### 原 XEX 直接复现实测

本次另建 `local/analysis/phase8/discovery-xex-reproduction/`，实际通过上述 `--xex`/`--loader-source` 内存路径运行：`exit=0`，逐字输出 `CALLBACK_SITE_AUDIT {"static-candidate": 17}`。结果 `callback-sites.json` 重开确认 `input_mode=hash-locked-xex-in-memory`、17 个 site、新树 mapping 17/17、完整映像 hash 与前述原像一致；目录只生成元数据 JSON，没有原像/密钥文件。`discovery-tests-input-modes.log` 保存 18 项合成测试 `OK / exit=0`。
