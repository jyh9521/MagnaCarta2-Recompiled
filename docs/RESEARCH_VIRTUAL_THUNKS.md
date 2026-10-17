# 原虚分派 thunk：823C2740 与有限候选扫描

## Verified：原始指令和真实 caller

工具 `tools/research/verify_thunk.py` 复用原 XEX 与 pinned loader-source 的完整 SHA-256 守卫，
只读展开原像，不写原文件、生成树、SDK 或 guest 对象。
`823C2740..823C2750` 是 16 bytes 的精确模板，SHA-256：
`0a315417a24fefd102c136c2b181f682cfa3b65422c9cbdaa146fd6caf719265`。

```text
lwz r11,0(r3)
lwz r10,12(r11)
mtctr r10
bctr
```

其语义是大端读取 `table=BE32[uint32(r3)]`，再读取 `target=BE32[table+12]`，
将目标零扩展至 r10/CTR，保持 LR 并尾分派。它不检查空指针，也不写内存；
不能把 null 对象解释成直接返回。它不是上一阶段的三个 store 叶回调，不赋予类名或构造函数语义。

原范围无包含它的 PDATA 记录；前一 thunk 在 `823C273C` 以 `bctr` 结束，后一函数从 `823C2750` 开始。
原 `.rdata` 中指向目标的三个大端地址是 `82156ADC`、`82156BB4`、`82156BF4`。
原 caller `[828C5040,+24)` 全范围 SHA-256 也受守卫：`828C5058` 读取表 `+8` 槽，
`828C5060 bctrl` 建立 LR `828C5064`，与阶段 6 真正 fatal 的 CTR/LR 一致。
进入本 thunk 后才读取下一层 `+12`，两次分派槽不是同一槽。

## Verified：有限扫描规则和结果

基线见证是阶段 6 `mc2_probe_init.cpp`，完整 SHA-256
`4eac8309956903d5d383f2d95abd1bbcb083d2386c12e74d277b38191a2b773b`；
工具拒绝未知或不完整 mapping。扫描读取原 PE32 section，而不是对整个原像任意 pattern 匹配。

只有同时满足以下条件才输出**静态候选**：

1. 精确四指令寄存器模板与上例相同，第二次 `lwz` 的 offset 可为非负、四字节对齐的槽。
2. 16-byte 全范围位于 executable section 内，指令地址四字节对齐。
3. PDATA 若覆盖，则必须恰为该地址起始的 16-byte 函数；不得落入其他 PDATA 函数内部。
   无 PDATA 时，前一指令必须为 `blr`、`bctr` 或无 link 的无条件 branch。
4. 原只读非执行、非 writable、非 discardable 的 data section 中有对齐大端指针引用。
   `.pdata` 的入口记录不计作独立对象/表引用；可丢弃 relocation/debug suffix 不参与。
5. 基线生成 mapping 中没有该地址。

当前原版本实际结果为 **1 个候选：823C2740**。完整名单及每项 section、边界、指针引用、
范围 hash 存于本地 `thunk-verification.json`。这不证明所有其他 thunk 均被识别：
其他寄存器模板、空指针保护、调整 this 指针、来自 writable 表的引用，以及无上述边界见证的函数都不在扫描边界内。
本工具不自动写 hint，不把静态候选当作已执行或已验证兼容。

## Verified：新原生成体的分派差分

新严格生成树中的原函数体位于 `mc2_probe_recomp.31.cpp:2826`：

- 源文件 SHA-256：`0f448f0f0780b4a4a2bc26156d3e449f3c8e56b1d9324321c6ad8e4cb3740172`。
- 原样 body SHA-256：`5436782a3448fac02561045b16663b41cfd6457b841994aa00bb3b5232532abe`。

独立有限 oracle 从受守卫的原四条 PPC 指令读取两字 fixture，输出 r10、r11、CTR、LR、
dispatch 目标与不变内存。缺失内存和未知指令模板明确失败，不推导未加载目标的行为。
本机 harness 原样编译生成 body，使用真实 SDK `PPCContext` 和大端内存宏；
**仅将外部 `REX_CALL_INDIRECT_FUNC` 边界替换为记录目标，不执行未知 callee**。
所以这是 thunk 的分派/状态差分，不是下游函数或整条真实标题路径成功证明。

四个用例包含目标 `12345678`、`00000000`、`FFFFFFFF` 和 `8234FF10`；即使零/无效目标也只记录，
不会在 harness 中调用。每例核对 r10、r11、CTR、64-bit LR、r3 和全部 4,096 bytes 内存不变。
实际 compile exit=0、run exit=0：

```text
THUNK_CASE 0 target=12345678 recorded=12345678 success=1
THUNK_CASE 1 target=00000000 recorded=00000000 success=1
THUNK_CASE 2 target=FFFFFFFF recorded=FFFFFFFF success=1
THUNK_CASE 3 target=8234FF10 recorded=8234FF10 success=1
```

EXE SHA-256 为 `d62a3d6015217647454fdf85bec53ae182ce8ccd456360becb50f8690229034e`。
生成树 400 files、SDK include 1,119 files、Clang resource headers 294 files、compiler、vcvars 和原输入
在实验后重新核对 hash，全部不变。MSVC/Windows 系统头与链接库未逐文件 hash 覆盖，
不宣称跨机器位级重现或未知虚调用目标兼容。

## 测试、日志与复现

```powershell
python -m tools.research.verify_thunk `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --mapping local/analysis/phase6/callback-codegen/project/generated/default-disc1/mc2_probe_init.cpp `
  --generated local/analysis/phase7/thunk-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' `
  --output local/analysis/phase7/thunk-generated-final
python -m unittest discover -s tests -p test_thunk.py -v
```

重跑选择不存在的新目录；省略 generated/sdk/compiler/vcvars 四项只做原静态检查，不标记为生成体执行。
公开合成测试 **15 tests / OK**，覆盖 pattern、边界、代码 section、只读引用、异常表排除、
缺 mapping、null dispatch 记录、无效内存和外部调用边界。负例明确报错，无静默 fallback。
实际子实验未出现额外编译/执行失败；`thunk-static-first`、`thunk-generated-first` 及最终
`thunk-generated-final` 均保留，不覆盖较早证据。最终日志 `thunk-tests-final.log`、`thunk-generated-final.log`。
原像、生成代码、harness、EXE 和完整候选 JSON 仅位于 ignored `local/analysis/phase7/`。

## 原标题越过本 thunk 后的下一真实入口缺口

完整新模块的原标题链已越过 `823C2740`。随后缺少电影/启动包的部署失败单独保留；
从原 ISO 向全新 `game-root-18` 严格验证暂存实际请求的 18 个原成员后，
`boot-staged/run.txt` 捕获新的 fatal：`ctr=82C1C1A0`、`lr=8286FE8C`、
`r3=FFC8AE30`、`r4=FFC8AE48`。日志仍可能包含原盘不存在的可选 `movie.xxx` 探测；
这里不把该探测或先前未补齐资产的失败归类为当前兼容缺口。

独立固定原 XEX 的只读检查确认：

- `82C1C1A0..82C1C228` 是完整 **136 bytes（0x88）/34 条指令** 的函数范围，
  无包含它的 PDATA 记录，也没有新生成入口 mapping。
- 原函数有两个 `blr`，位于 `82C1C210` 与 `82C1C224`；当前树却登记了内部尾块 `82C1C214`。
  下一函数从 `82C1C228` 的标准序言开始。因此仅为内部尾块建立映射不覆盖真实调用入口或完整控制流。
- 原像未发现对齐的静态大端 `82C1C1A0` 指针。地址通过指令构造：
  `82C35478 lis r11,82C2`，`82C35480 addi r6,r11,-3E60`，
  `82C3548C bl 8286FD30` 传入 r6，r5=4。
- 原 `8286FD30` 将 r6 保存为 r25；`8286FE74 mtctr r25`、
  `8286FE88 bctrl` 的返回地址 `8286FE8C` 与现场完全一致。

该回调不是前节四指令 thunk。静态数据流显示两个参数各先解引用一个对象指针，
再遍历对象 `+32` 的链表；节点 `+4` 是下一指针，节点 `+0` 指向被再次解引用的 word。
函数对 `(word >> 13) & FFFF` 求每条链的无符号最大值（空链为 0），
两最大值相等返回 0，第一条较大返回 -1，第二条较大返回 +1。
该结构与比较排序回调一致，但对象/字段名称、排序函数原符号身份及实际链表内容尚未核定。
**这个新回调仍未执行**：本次运行在入口 mapping 查找处失败，不把静态语义当作原对象已经正确比较的证据。

范围 hash、原始有界指令、mapping/PDATA、地址构造和实际日志身份保存在
`next-blocker-initial.json`、`next-blocker-inspection.txt`、`next-blocker-address-construction.txt`。
本阶段不新增该目标的 hint，不修改生成代码或原数据绕过它；
下一阶段应按完整 0x88 范围恢复入口和双返回控制流，再严格重生、差分与原标题重跑。
