# PPC 条件分支与 SEH 函数边界修复

## 固定输入与上游

- 盘 1 XEX SHA-256：`26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f`。
- ReXGlue 0.10.0 / Tom Clay，commit `f5337cdc947ff6d4c4196737e2c807a48f2a1fc2`；使用官方原包，不修改分析器、SDK 或游戏指令。
- 独立映像展开依据 Xenia / Ben Vanik and contributors，commit `95a5c3ee250f80c3b9d139658649d9ffb6db3eec` 的 `src/xenia/cpu/xex_module.cc` 与 `src/xenia/kernel/util/xex2_info.h`。沿用仓库已下载的 `local/upstream/xenia/xex_module.cc`，SHA-256 `36a30e1bc54b9854cbd2572b74e366e733460c5df6edf2b29542de36575858f2`。
- 上游原源码/许可证留在忽略目录；公开工具不包含密钥常量、不会输出密钥、签名或完整映像。真实独立校验需安装 `cryptography`（本机 46.0.3）；CI 合成测试不需要此包。

## Verified：原生 PPC 的共享 early-return 块

原 XEX 只读展开后，以下两个连续范围均为 0x38 bytes：

|入口与排他结束|原生控制流|
|---|---|
|`82CE6748..82CE6780`|先取 `r3+712`；非空走 `82CE6754` 的 `lbz +468` / low-bit 返回；为空依次检查 `r3+708`、`r3+716`，任一非空后向跳回同一块；全空返回 0。|
|`82DA3488..82DA34C0`|先取 `r3+80`；空走 `82DA3494` 返回 0；非空再取该对象 `+124`，为空后向跳回同一返回块；否则加载对象 vtable `+284` 并 `bctr`。|

三条原始条件分支字分别为 `409AFFEC`（`82CE6768`）、`409AFFE0`（`82CE6774`）、`419AFFF0`（`82DA34A4`）。独立按 PPC BC 位段计算的目标依次为 `82CE6754`、`82CE6754`、`82DA3494`。

**High-confidence deduction：** ReXGlue `phase_gapfill.cpp::splitRegionOnTerminators` 按每条 `blr` 切分未覆盖区域，将 early-return 后的代码另登记为函数；原代码真实后向跳转仍指向被切走的共享块。三条 `REX_FATAL` 是边界误恢复的结果，不是游戏本身的断言。以两入口显式 `size=0x38` 重生，保留全部指令，不增加 stub，不把条件改成无条件。

配置独立保存为 `research/xex/disc1-control-flow.toml`，阶段 2 配置与生成树不覆盖。

## Verified：全模块编译发现另一类 SEH 边界问题

首次全量编译发现 5 个函数共 10 条 goto 引用了未定义标签。原映像中的 `.pdata` 给出以下精确大小；每组首段末尾是指向 `82A560C8` 的 `bl`，紧随两个描述字而非正常执行指令，下一段从 `start+0x9C` 开始。

|首段入口（size 0x94）|下一 funclet（size 0x54）|第三段（size 0x28）|
|---|---|---|
|829335B4|82933650|829336A4|
|82934134|829341D0|82934224|
|82927154|829271F0|82927244|
|829183A8|82918444|82918498|
|82938758|829387F4|82938848|

旧代码生成曾把描述字当 PPC，并重复拼入下一 funclet 的前半段，遗漏循环后的 label；不能通过补一个空标签来掩盖。控制流配置对前两段给出 PDATA 精确大小，并设置上游 `share_registers=true`，保留 funclet 从所属函数继承的 ctx 非易失寄存器状态。第三段已有正确独立边界，不作额外配置。

## 验证边界与复现

`verify_branch_ranges.py` 先锁定 XEX 与上游 loader 源码 SHA，再独立展开、核验两个完整指令范围、3 条分支位移和 15 个 PDATA 记录。它不会编辑 XEX、ISO、SDK 或生成源。

`execute_leaf()` 是有限 PPC 指令集的独立测试 oracle，不是游戏模拟器：合成内存共 27 组输入覆盖三条问题分支 taken/not-taken 与原 early-return 路径；未供给的内存读或未知指令立即失败。`bctr` 仅记录间接调用目标，不执行游戏原生函数。另有生成函数内 label/goto 与 `REX_FATAL` 静态核验。这些不证明画面、启动或运行时完整语义。

干净 checkout 的重新生成入口（保持新输出目录，严格验证、不使用 `--force`）：

```powershell
python tools/research/probe_branch_codegen.py --iso 'MagnaCarta II (Korea) (Disc 1).iso' --sdk-zip local/upstream/rexglue/sdk.zip --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe --loader-source local/upstream/xenia/xex_module.cc --output local/analysis/phase3-route-a-reproduction
python -m unittest discover -s tests -p test_branch_ranges.py -v
```

独立核验既有实验：

```powershell
python tools/research/verify_branch_ranges.py --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --generated local/analysis/phase3/branches-bounded/project/generated/default-disc1 --output local/analysis/phase3/branch-verification-repeat.json
```

## 实际实验记录

- 阶段 2 原始三条 `REX_FATAL`、MSVC 失败、两入口 hint 及 397 文件生成记录全部保留。
- `local/analysis/phase3/branches/`：先仅纠正两个 early-return 范围的严格重生迭代；包含原始控制流配置快照、codegen 日志、PPC/PDATA 独立验证 JSON。
- `local/analysis/phase3/branches-bounded/`：追加 SEH PDATA 范围的第二次严格重生；包含独立配置副本、命令、退出码、持续时间与日志。
- 全模块基线构建与错误日志见 [模块构建实验](EXPERIMENT_MODULE_BUILD.md)。所有失败均保留，未把 exit=0 生成冒充可编译、可链接或游戏运行成功。

### 第一轮：三处分支修复已验证

`branches/project` 严格生成 `exit=0`，337.8 s，`397 written`，没有未解析条件分支 warning。两函数真实生成体保存于 `branches/generated-branch-bodies.json`：

- `sub_82CE6748`（TU 189）包含 `loc_82CE6754`、两条 `if (!ctx.cr6.eq) goto loc_82CE6754;`，无 `REX_FATAL`。
- `sub_82DA3488`（TU 102）包含 `loc_82DA3494`、`if (ctx.cr6.eq) goto loc_82DA3494;`，无 `REX_FATAL`。

此轮只含两个 early-return 的显式边界，不含随后发现的 SEH 修复；因此不能作为最终全模块编译通过证据。

### 第二轮：PDATA 精确边界后静态控制流完整

`branches-bounded/project` 严格生成 `exit=0 / 328.7 s / 397 written`。197 个 `.cpp` 中，195 个是重编译 TU，另两个是映像/映射支持 TU。`verify_branch_ranges.py` 实际对全体重编译函数核对 goto 目标存在，结果为 0 个未定义 label；全生成重编译源码 `REX_FATAL` 为 0。两叶函数的全部 5 条条件 goto（含修复的 3 条与原 forward 2 条）及目标 label 均核验正确。独立结果：`local/analysis/phase3/branches-bounded/branch-verification.json`。

实际宿主叶函数实验读取此次真实生成函数体，使用 SDK 原 `PPCContext`、CR 比较和 PCH big-endian 内存宏，仅在 `REX_CALL_INDIRECT_FUNC` 的外部调用边界记录目标（不调用游戏函数）。首次严格编译/运行均 `exit=0`，输出 `GENERATED_BRANCH_HARNESS cases=27 passed=27`；与 27 组独立 PPC oracle 对照一致。全模块再次编译及最终叶函数复测结果由模块实验记录维护。原 XEX/SDK 不改，宿主夹具并非完整游戏。

生成、字节校验、oracle、宿主夹具和全模块构建分别属于独立验收层；当前没有据此声称链接主程序、图形/音频、启动、存档或换盘通过。
