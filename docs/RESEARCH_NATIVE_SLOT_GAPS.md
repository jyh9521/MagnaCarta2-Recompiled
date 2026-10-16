# GNatives 运行表与历史静态清单：01 / 52 / 61 差集

日期：2026-10-17。只读对账，不改历史提取模板、SDK、原像、生成树或函数 hint；本报告不增加/执行 61。

## 被对账的输入与身份

历史 `local/analysis/phase4/native-registration-disc1-final.json` 是**特定 31 指令 ctor 模板且目标已 generated 的静态恢复结果**，不是 GNatives 全量实现承诺。其 299 个 index 均有 original-image 依据，但报告明确 `not-executed`。

运行期输入采用独立真实运行 `local/analysis/phase8/boot-independent/` 的 `title-natives.bin`，并联合 `title-entry.json`、`run.json`、`run.txt` 核验身份；不只信任孤立二进制文件名或旧 `next-blocker-native-gap.json` 的摘要。

|输入|SHA-256|
|---|---|
|`local\analysis\phase4\native-registration-disc1-final.json`|`076f6082e4a2b6b4dc61b0acf9b1262fb0b11485c19c48208e4ada6385e335c7`|
|`local\analysis\phase8\boot-independent\title-natives.bin`|`18bbcd6431f1e0949f2990e31ca60fad5f838afd2e47daf1377f55458c36b5be`|
|`local\analysis\phase8\boot-independent\title-entry.json`|`aca68773a020115325c13f1eb39b70cde5213b1f7f70581d3fbe84bb6879864c`|
|`local\analysis\phase8\boot-independent\run.json`|`00fb21f09a9c9d1b33844b75d8acf309b4e0f258ba2054516b39264b7bd5619d`|
|`local\analysis\phase8\boot-independent\run.txt`|`c10405c396e7b5fbef891e20e8eee63a1598653689a529e076cb74c002d8db2a`|

原 XEX SHA-256 为 `26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f`；完整原映像 SHA-256 为 `d18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9`。运行报告证明原像加载、入口启动、输入未改；此进程最后为 `0xC0000409`，并非游戏启动成功。快照固定为 **4096 个大端 32-bit 槽、16,384 bytes**；fallback `82505980` 共 3794 槽，非 fallback 302 槽。

对应真实日志行是：

```text
TITLE_NATIVES guard=1 bound=4096 fallback=3794 int_const=82508E60 add=8250BAF0
```

`phase8/next-blocker-native-gap.json` 来自较早 `boot-guidcache`，快照 SHA 与独立运行完全相同。本文另对独立运行五件输入重新读取/散列，不把先前摘要当作独立证明。

## Verified：299 与 302 的精确差集

|index|运行表目标|历史 299 内|阶段 8 mapping|阶段 9 仅增加 52 后 mapping|
|---|---|---|---|---|
|01|82505A60|无|有|有|
|52|82509380|无|无|有|
|61|82517D70|无|无|无|

原 299 项全部仍 active、实现地址与运行快照逐项相同：**0 个 mismatch、0 个失活**。差集恰为上表三项。运行注册完成/快照存在不等于执行了 302 个 handler；只有本阶段主实验实际触发的 52 入口另有执行证据，61 本报告仍只作静态分析。

用**未修改**的 `recover_initializers()`，只把 generated-entry 集合换成阶段 9 严格新树，得到 300 项：仅多出 52，原 299 项所有字段保持一致。01 依然因模板变体遗漏，61 仍因没有 generated 入口被拒绝。这个 300 也是静态模板层计数，不与 302 混称。证据 `native-gap-static-new-mapping.json`。

## 01：已生成，遗漏原因是 ctor 的寄存器分配变体

原处理入口 `82505A60` 有 PDATA 精确边界 `+0x98`，已有真实 generated mapping。原 ctor 是 `82E6EEC8..82E6EF44`（0x7C bytes），source pointer slot `8320B650` 含 `82505A60`，写入目的为 `83250D80+4`。

旧模板固定以 r8 作 GNatives 基址、r10 作 source、r9 作 duplicate-index 辅助基址。01 的原指令以 **r10 作 GNatives 基址、r9 作 source、r8 作辅助基址**：`82E6EED0 addi r10,r10,0xD80` 与旧 `addi r8,r10,0xD80` 首先就不同，其余 guard/source/store 对应寄存器也随之变化。

因此它没有满足旧模板的 `fixed` 字典；不是“runtime 伪造新增 native”、不是缺 handler，也不是从索引猜一个 PC。这里仅记录该已核验变体，不修改旧模板为泛化弱匹配。

## 52 与 61：同属 tail-dispatch gateway，不同参数/表来源

两者原 ctor 都符合旧模板的指令形状，且 source pointer 能从原像读出正确目标；历史拒绝发生在 `target not in entries` 的入口边界守卫。原 52 ctor `82E710C8` 读取 `8320B760`；原 61 ctor `82E78008` 读取 `8320BAD4`。旧提取器保守拒绝未知目标是其既定范围，不应删除守卫以把 299 强凑 302。

### 52 / 82509380

原范围 `82509380..82509398` 是 0x18 bytes，6 条指令，无包含它的 PDATA。它从 `r4+8` 取值放入 r3，经 `83250980+0x118=83250A98` 读取另一个函数地址，`mtctr/bctr` 尾分派。该槽**不是 GNatives 基址 83250D80**；不把这两个表混为一谈。实际语义/夹具和宿主启动进展见 [native gateway 实验](EXPERIMENT_NATIVE_GATEWAY.md)。

### 61 / 82517D70

原连续范围 `82517D70..82517D9C` 为 0x2C bytes，11 条指令，末尾 `bctr`；下一 word `82517D9C` 为零 padding，`82517DA0` 开始相邻的另一段同类分派代码。PDATA 无包含记录。这些是**有界原指令/末端证据**，不是已经由实际执行或完整调用图证明的函数身份。

原指令读取 `BE32[r4+12]` 得到字节码指针，取一个 unsigned byte t，并将 frame 指针前移 1；随后从 `GNatives+0x400+t*4` 取目标并 `bctr`。即索引为 `0x100+t`（0x100..0x1FF）。与现有字节码 reader 的 extended-native `0x61` 编码相符，但本报告不以 VM token 名称替代原指令证明。r3/r4/r5 原参数保留，LR 由尾跳保留；这里没有执行未知 callee。

**High-confidence deduction：** 61 是扩展 native 索引的 tail-dispatch gateway；52 是另一个固定槽/上下文调整的 tail gateway。二者同属短分派入口、无 PDATA、曾无 mapping，但不是同一个函数或可共用同一替换 stub 的语义。61 没有被本阶段新增 hint，也未据相似外形自动生成入口。

原像中的有界证据：

|范围|地址/长度|SHA-256|
|---|---|---|
|index01-initializer|`82E6EEC8+7C`|`7195ca73ec6424d2d69b1a265a59ad6a28cbb907a4310185a9092b14f84097c2`|
|index52-initializer|`82E710C8+7C`|`3dd929abe42091fe2511c77947f3ead953f33ce0cf7239ec2c1c49adfa4e8eee`|
|index61-initializer|`82E78008+7C`|`fcc0646f0b0add7abd3448d87ce12ab8c2c2428d6f40494fac3597b31812680a`|
|index01-handler|`82505A60+98`|`b26d7433607979e66242ea266b8968deda18d5d6d5db9fed5661687bffb65a61`|
|index52-gateway|`82509380+18`|`24858452f74ebfe37c65055b81249f2b52a972d7f8374451f2b260775436bad2`|
|index61-gateway|`82517D70+2C`|`b628e1746cfef4cd7c8340ad46cddaaf9fe16e6a083111c11983d7e43c6ce471`|

对照旧提取器源码 SHA-256：`3e2646d552546785cf8a06d9b46f03adbc28cc826928effce5575357a1685dde`；指令原像、PDATA、ctor source slots 与生成 mapping 分别核验。反汇编展示来自已安装 Capstone 5.0.7，只留本地证据，不作为新增运行时依赖；对账工具和合成测试仅用标准库。

## 可复现的显式输入合同

工具 `tools/research/reconcile_native_slots.py` 只读取显式五件输入及可选 generated register；不依赖本地原像文件、数据库、私有 API 或目录猜测。输入角色如下：

- `--static-report`：由 [native registration 流程](RESEARCH_NATIVE_REGISTRATION.md) 重建或提供的**历史 299 模板清单**；严格检查 schema/profile、原像身份、299 唯一 index/initializer、地址对齐/原可执行段、source slot 范围及全部 template evidence 字段。
- `--snapshot`：由 [实际入口探针](EXPERIMENT_NATIVE_GATEWAY.md) 的真实运行产生的 `title-natives.bin`；只接受固定 4096 大端槽长度，不接受凭数值列表冒充快照。
- `--runtime-report`、`--run-report`、`--run-log`：同次运行的 `title-entry.json`、`run.json`、`run.txt`。核对快照/日志 size 与 SHA、原 XEX、真实启动/输入稳定 flags、进程 exit status、4096/guard/fallback/int_const/add 摘要和唯一实际日志行。
- `--generated-register`：可选，只报告 mapping 状态，不将 mapping 当执行。仅接受明确 `SetFunction(address, sub_address)` 地址一致/无重复的条目。

快照和运行报告不是公开仓库预装文件；clean checkout 使用者先按链接的公开工具从用户原 XEX/资源复建并运行探针，将输出路径传入即可。也可对已有本地证据作明确输入复核；工具没有默读旧 phase 目录。

实际本轮命令：

```powershell
python -m tools.research.reconcile_native_slots --static-report local/analysis/phase4/native-registration-disc1-final.json --snapshot local/analysis/phase8/boot-independent/title-natives.bin --runtime-report local/analysis/phase8/boot-independent/title-entry.json --run-report local/analysis/phase8/boot-independent/run.json --run-log local/analysis/phase8/boot-independent/run.txt --generated-register local/analysis/phase9/gateway-codegen/project/generated/default-disc1/mc2_probe_register.cpp --output local/analysis/phase9/native-gap-phase9-reconciliation.json
python -m unittest discover -s tests -p test_native_slots.py -v
```

两次对账分别使用阶段 8/9 的 register，均 `exit=0`，逐字输出：

```text
NATIVE_SLOT_RECONCILIATION runtime=302 static=299 missing=3 mismatches=0
```

18 项合成测试 `OK / exit=0`，含错误快照长度/hash、错误原像/XEX、bool/越界/重复 index、错误目的字段、非代码地址、run/log 不同源、缺启动 flag、错误摘要、重复 JSON 字段和错误 mapping 地址负例。所有身份/结构验证先于输出；输出用独占新文件，不覆盖现存文件或输入。

## 当前知识边界

元数据与散列能绑定**同一份观测证据**，不对任意伪造的自洽 JSON 提供密码学真实性认证；本文实际结论还绑定上列已保存报告 hash。工具不解释函数 ABI，不把相同实现地址、已登记或已初始化等同于逐个 handler 执行，更不据差集自动添加 hint。

`local/analysis/phase9/native-gap-*` 保存完整输入 SHA、原指令见证、旧/新 mapping 对账、原 299 到新 300 静态变化与测试日志。52 的修复和回退由主阶段执行；本对账研究不单独证明61运行；随后主阶段boot-titlemap与独立重跑已实际触发61查找失败（见PHASE9_RESULTS及网关研究），但61本体、下一byte、下游及兼容闭包仍未执行验证。
