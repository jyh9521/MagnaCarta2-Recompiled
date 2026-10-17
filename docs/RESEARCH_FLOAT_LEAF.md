# 原始 float 叶入口与生成转换差分

## 范围与证据级别

Verified：原 Disc1 XEX、loader 的既有 SHA 守卫通过后，`82AC1DE8..82AC1DFC` 恰为20bytes：`c0030030d0040000c0030034d00500004e800020`，SHA256 `579d0af704a9e2c35ba6dc55ffe769344f780cf91ddc302e77aa72da6071ab53`。五条指令依次是 `lfs f0,0x30(r3)`、`stfs f0,0(r4)`、`lfs f0,0x34(r3)`、`stfs f0,0(r5)`、`blr`。

没有包含此入口的原 PDATA。保守20-byte leaf 边界由实际结尾 BLR、前一兄弟尾跳 `82AC1DE4 bctr`、后一零 word `82AC1DFC` 及 `82AC1E00` 独立短叶支持，不标记为 PDATA/整个类边界。阶段12实际 fatal 的 CTR=`82AC1DE8`、LR=`8266CC78`；原 `8266CC74 bctrl` 从 object vtable+0x20 取目标，caller PDATA=`8266C0A8..8266CD80`。完整证据仍保留在 `local/analysis/phase12/next-blocker-original.json`。

本工具不加 hint、不改生成树或 SDK；独立新树入口恢复由另一个有守卫生成实验负责。叶夹具成功不是完整标题、资源加载、可玩或 Xenon 硬件验收。

## 转换、顺序与副作用

High-confidence deduction：按五条原指令，先读 object+0x30，再写 r4 指向的32-bit值，**之后**才读 object+0x34 并写 r5。`r4==r3+0x34` 会改变第二次读取；`r4==r5` 最后一写覆盖第一写；输出指向第一输入也不能提前快照两个 source。未建模 MMIO、无效地址、异常、非对齐访问或并发数据竞争。

独立 `widen32` / `narrow64` oracle 全用整数：分解 sign/exponent/fraction，精确正规化 binary32 subnormal，采用 binary64 的显式位表示；收窄采用 nearest-even 舍入及 gradual underflow，保留 signed zero、infinity。NaN 有 `preserve` 和 `quiet` 两个**显式模型策略**，保留 sign、高位 payload；quiet 策略设置 quiet bit。对本叶从32-bit载入的精确值，除 NaN 策略外，32→64→32 应往返。

这不是所有 PPC/FPSCR 模式、NaN payload 或 sNaN trap 的硬件规范证明。真正差分预先固定 **quiet 模型**，失败不自动换策略拟合；`preserve` 用来区分格式模型，而非豁免实际失败。模型最后一个 FPR0 是第二次读取转换的64-bit值；原指令不修改 GPR/CR/LR/CTR。生成 SDK 另有 host浮点控制副作用，单列检查。

Verified：本轮实际生成 body 使用 `ctx.f0`，第一 lfs 调用 `ctx.fpscr.disableFlushMode()`，通过真实 BE U32 macros/union float/double 转换，不是 memcpy。SDK `context.h` SHA256 `5f84d78c38cf626cf4c8107293cd9824f6e8cf81225f201b608505698273dc36`、`platform/fpscr.h` SHA256 `e1f98e71630e8dc9efaae4db831679c64273419d612256d76193fb5bd8930adb`：x86 flushmask=8040（FTZ+DAZ），cached csr 是 host控制字，不是完整 guest FPSCR。每个夹具设置真实 MXCSR 后调用官方 `InitHost()`，使 cached 与 host 状态一致；测试四种 round bits × 四种 flush bits。真实 host sticky flags 单独记录、不假装是完整 guest异常标志。

固定 [Xenia95a5c3ee 的 lfs/stfs frontend](https://raw.githubusercontent.com/xenia-project/xenia/95a5c3ee250f80c3b9d139658649d9ffb6db3eec/src/xenia/cpu/ppc/ppc_emit_memory.cc) 与 [x64 lowering](https://raw.githubusercontent.com/xenia-project/xenia/95a5c3ee250f80c3b9d139658649d9ffb6db3eec/src/xenia/cpu/backend/x64/x64_sequences.cc) 同样使用32↔64 conversion；这些上游实现不是硬件执行证明。本地逐文件hash和审查范围在 `fp-sdk-independent.json`，未把另一版本源码当作打包 SDK 实现。

## 已验证：实际生成 body 的三种编译实验

CLI 对 fresh generated 中唯一完整 `sub_82AC1DE8` body、init mapping 与 registrar 一对一检查，记录 body/source/PCH和SDK include tree hash。原 body 原样进入本地 harness；没有替换 FP或内存 macro、没有stub，也没有禁用优化规避问题。

每配置768夹具：12种含 signedzero、normal、subnormal、infinity、signed quiet/signaling NaN 的输入组合 ×4别名布局 ×4round ×4flush。两个稀疏 guest页在低地址 `2000` 与高地址 `FFFEE000` 交替使用真实地址映射；活动页4096bytes全部比较，另一页必须保持 A5。完整 PPCContext 按字节比较（仅预先允许 f0 与清flush的cachedCSR变化），GPR/CR/其它FPR/向量/LR/CTR均覆盖；每例恢复 hostCSR。

|实际 flags|compile/run exit|结果|
|---|---|---|
|`/Od`，无 `/fp:strict`|0/0|768通过|
|`/O2`，无 `/fp:strict`|0/1|608通过、160 memory差异；context及mode检查仍通过|
|`/O2 /fp:strict`|0/0|768通过|

最终证据：`local/analysis/phase13/float-od-final.json`、`float-o2-final.json`、`float-o2-strict.json` 及各自 `*-harness/verification.json` / `compile.txt` / `run.txt`。初次 Od/O2 输出也原样保留，没有覆盖失败。

例如 rawO2 case448，输入第二值 `7F812345`，预定quiet模型应输出 `7FC12345`，实际仍为 `7F812345`；最终 ctx.f0 为 `7FF82468A0000000`，已quiet。日志逐字为：

```text
FLOAT_CASE 448 memory=0 context=1 mode=1 ctx_f0=7FF82468A0000000 out1=7F800000 out2=7F812345 host_csr=00001F81 cached_csr=00001F80 success=0
FLOAT_MEMORY pages=2 released=1 failures=160
```

Verified：实际 COFF函数定义 `__imp__sub_82AC1DE8` 机器码在 `float-machine-code-final.json` 固定对象hash：Od含两组 `vcvtss2sd/vcvtsd2ss`；rawO2只保留两条 `vcvtss2sd`，store路径的回转转换被消去；O2strict两组conversion均存在。首次把弱外部alias `sub_82AC1DE8` 的 section0 当作section-1，误读 `.pdata`；该无效尝试保留 `float-machine-code-first.json`，最终按实际定义+EXECUTE section守卫纠正，不能把旧反汇编当证据。机器码解码使用本地 Capstone5.0.7，仅诊断，不是工具/test依赖。

实际模块原 flags 无显式优化（Od）；rawO2不能视为支持的浮点构建配置。显式 strict诊断证明此夹具集的差异消失，不等于所有浮点指令、NaN或 FPSCR硬件等价；完整模块编译/标题运行以独立阶段13报告为准。

## 复现与失败保留

```powershell
python -m unittest discover -s tests -p test_float_leaf.py -v
python -m tools.research.verify_float_leaf --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --output local/analysis/float-reproduction/original.json
# 可选真实body差分：四项工具链参数必须一起给出；默认Od。
python -m tools.research.verify_float_leaf --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --generated local/analysis/phase13/strict-codegen/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --optimization O2 --fp-strict --output local/analysis/float-reproduction/o2-strict.json
```

输出必须为新文件，harness自动使用旁边 `<output-stem>-harness` 新目录；不在原 XEX/loader/生成树/SDK或compiler树中输出。源码/头/工具链前后hash复核保留。纯整数工具与标准库tests不依赖 SDK、游戏或 hostfloat支持；真正XEX解码复用有hash守卫的既有loader入口（cryptography依赖），不保存原像或密钥。

真实原版CLI exit0、24格式向量完成；对自制 unsupported XEX 实际 CLI exit1，逐字 `ValueError: unsupported XEX hash`，无输出文件，保留 `float-leaf-guard-failure.json`。测试覆盖随机格式往返、host finite交叉核验、ties/overflow/underflow、NaN策略、别名顺序、FPR0、未知输入/编译flags、缺body/重复body/错误mapping及半套工具链。所有失败记录均保留，没有把拒绝或差分不符改写成成功。

最终 CLI 将标题执行字段明确写为 `title_runtime_execution=NOT-TESTED`，生成函数差分另列 `generated_execution` 和 compile/run status；先前本地报告的旧 `runtime_execution` 指标题未验收，历史文件不覆盖。
