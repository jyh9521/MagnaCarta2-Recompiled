# 8234FF10 间接回调入口：原指令与生成体差分

## Verified：原始边界与指令语义

`tools/research/verify_callback.py` 使用既有原 XEX、pinned Xenia loader-source SHA-256 守卫，
只读展开原像。原入口范围 `8234FF10..8234FF40` 为 48 bytes、12 条指令，SHA-256：
`5c43c892cc33dcb8b15d083257e0a8211788bb01aaa0698cd379c2164e77665e`。
原 PDATA 无包含该地址的记录；阶段 5 生成树也未登记它。

它首先以 `cmplwi cr6,r3,0` 检查对象地址低 32-bit；为零时直接返回，不读写对象内存。
非零路径的三个原 `stw` 依次是：

|次序|写入地址|大端 32-bit 值|
|---:|---|---|
|1|`r3+132`|`82124644`|
|2|`r3+0`|`82124FC0`|
|3|`r3+132`|`82125118`|

第三个 store 覆盖第一个值；仅比对最终内存会漏掉第一条写入，因此静态顺序和运行最终结果分别验证。
临时寄存器 r6–r11 的 `lis/addi` 使用 64-bit 符号扩展；r3、LR 和其余 GPR 不变。
工具不根据三个地址擅自赋予类名、对象身份或构造/析构语义。

地址来源和实际失败点也有各自完整原指令范围 SHA-256 守卫：

- `[82D6C814,+34)`：`lis r6,8235`，`82D6C834 addi r9,r6,-00F0` 构造 `8234FF10`，
  随后 `82D6C844 bl 823A6150` 将该值作为 r9 参数传入。
- `[823B9AF8,+24)`：从来源对象 `+284` 获取间接目标，`823B9B18 bctrl` 的返回地址为 `823B9B1C`，
  与阶段 5 真实 fatal 的 CTR/LR 一致。两条分支的相同 `+284` 读取均保留在见证范围内。

完整写入数据流尚未逐步追踪，所以不把静态地址构造与实际对象槽直接宣称为已执行的一条完整链。
阶段 5 的来源记录见 [启动链研究](RESEARCH_STARTUP_CHAIN.md)。

## Verified：真实新生成体执行

阶段 6 为新严格生成树增加显式原版本入口 hint，仍由 ReXGlue 产生函数体。
本实验只读取得 `mc2_probe_recomp.41.cpp:1591` 的完整 `DEFINE_REX_FUNC(sub_8234FF10)`：

- 生成文件 SHA-256：`fb5802d006c1e86ac5e5b8b688c1ef22a6d8480c3c4dc53c9686e7e5b9e23da7`。
- 原样函数体 SHA-256：`504214a001f756b1ea1be0f2eddd4a1679eceb815220c22f6f7d5b01daaeaba3`。
- SDK 为已记录 ReXGlue v0.10.0，Clang 为已固定 20.1.8；没有改写函数、SDK 内存宏或间接调用宏。
  此叶函数没有间接调用，不需要 stub。

独立有限 PPC oracle 只实现本叶所需的 compare/conditional-return/lis/addi/stw/return 指令子集；
未知指令、未定义条件、越界内存和缺返回均明确报错，不是完整 PPC 模拟器。
5 个输入分别为 r3=0、100、180、400、F78，每组使用不同的 4,096-byte 内存保护模式和 32 个 GPR 种子。
真实 SDK 生成体在单独本机 EXE 中执行，逐项核对**全部 32 个 64-bit GPR、全部 4,096 bytes、LR 和 CR6.eq**。
`F78` 用例覆盖最后一个合法 store，null 用例核对零写入及全部寄存器保持。
原指令的顺序 store trace 由 oracle 给出，生成源的三条 store 与之交叉检查；本机执行验收核对最终状态，
不声称记录到真实 guest 硬件的三次写总线事件。

实际 compile exit=0、run exit=0，逐字输出：

```text
CALLBACK_CASE 0 r3=00000000 success=1
CALLBACK_CASE 1 r3=00000100 success=1
CALLBACK_CASE 2 r3=00000180 success=1
CALLBACK_CASE 3 r3=00000400 success=1
CALLBACK_CASE 4 r3=00000F78 success=1
```

EXE SHA-256：`994def9e677498561a07eaac11a03f5d2e7c9edcdd4c1368e733383e48128782`。
所有原始输入，以及生成树 400 files、SDK include 1,119 files、Clang resource headers 294 files、
compiler 与 vcvars 的身份在实验后重新核对。MSVC/Windows 系统头和系统链接库没有逐文件哈希覆盖，
所以不宣称跨机器位级重现。独立叶实验不代表完整标题成功或所有回调兼容。

## 失败保留与复现

初次实验的 harness 在同一作用域五次声明 `bool good`，编译器明确报重定义，compile exit=1；
保存在 `local/analysis/phase6/callback-generated-first/`，没有覆盖或删除。
修复只为每个测试输入建立独立局部作用域，新增对应回归测试；未修改生成体。
随后 `callback-generated-final/` 编译/执行通过；再加入完整头树身份守卫，
最终 `callback-generated-verified/` 仍通过，EXE hash 与前一次相同。

```powershell
python -m tools.research.verify_callback `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --generated local/analysis/phase6/callback-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' `
  --output local/analysis/phase6/callback-generated-verified
python -m unittest discover -s tests -p test_callback.py -v
```

输出目录必须是新的；复测时选下一个新目录名。仅去掉四个 toolchain 参数即可执行原像静态检查，
不会把未请求的生成体执行记为成功。最终实测日志 `callback-generated-verified.log`、
`callback-tests-verified.log`：13 tests / OK、exit 0。
实验 harness、生成文件、完整原像和 EXE 只在 ignored local 目录，公开仓库仅保留工具、合成测试和本说明。

## 实际标题推进后的下一阻塞

完整新模块继续执行原标题链后，旧 `8234FF10` fatal 已被越过；
新的真实 fatal 目标是 **823C2740**，PPC `ctr=823C2740`、`lr=828C5064`、
`r3=4037CF90`、`r4=34`。主流程的实际运行证据由标题探针另行记录，
本节的原像检查只读执行，不补新 hint、不改原数据或 SDK。

独立原 XEX SHA 守卫下，`823C2740..823C2750` 为 16 bytes、4 条原始指令，SHA-256
`0a315417a24fefd102c136c2b181f682cfa3b65422c9cbdaa146fd6caf719265`：

```text
lwz r11,0(r3)
lwz r10,12(r11)
mtctr r10
bctr
```

它是通过对象首字指向表的 `+12` 槽进行**尾分派**的独立 thunk，保持传入 LR，
不是上一节的三 store 回调，也没有证据赋予它构造函数语义。
前一独立 thunk 从 `823C2730` 开始、在 `823C273C` 以 `bctr` 结束；
后一函数从 `823C2750` 开始。该目标无包含它的 PDATA 记录，新的生成 mapping 中仍无登记。
原像中明确引用它的三个大端指针地址是 `82156ADC`、`82156BB4` 和 `82156BF4`。

实际 caller 的原指令 `828C5054` 读取对象首字、`828C5058` 读取表 `+8` 槽，
`828C5060 bctrl` 建立返回地址 `828C5064`，与现场 LR 一致。
**823C2740 原 thunk 尚未执行**：当前运行在查找该入口的 generated mapping 时就已 fatal；
它将使用的下一层 `+12` 目标只能由实际对象表值确定，不能凭相邻静态表猜定已执行的下游函数。

原像 hash、范围 hash、mapping 缺失、指针引用与 caller 范围见
`local/analysis/phase6/next-blocker-initial.json`；窄范围原指令记录为 `next-blocker-inspection.txt`。
本阶段仅定位这道新的入口覆盖缺口，未为它增加配置或绕过函数。
