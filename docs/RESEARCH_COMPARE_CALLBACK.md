# 双返回比较回调 82C1C1A0：边界恢复与差分

## Verified：原指令范围、地址构造、真实 caller

`tools/research/verify_compare_callback.py` 使用原 XEX 和 pinned loader-source 的完整 SHA-256 守卫，
只读展开并固定以下指令范围：

|范围|长度|作用|
|---|---:|---|
|`82C1C1A0..82C1C228`|136 bytes|完整比较回调，SHA `60e3229fb7c29acb4ca50ea10e03bf77af7d9e361a9882d12b2f8e7e9ad3388f`|
|`82C35478..82C35490`|24 bytes|r6 构造目标地址后传入 `8286FD30`|
|`8286FE70..8286FE90`|32 bytes|r25→CTR→`8286FE88 bctrl`，返回 LR=`8286FE8C`|

原函数无包含它的 PDATA 记录；在 `82C1C210` 和 `82C1C224` 各有一个 `blr`。
阶段 7 的完整生成 mapping 文件受固定 SHA 守卫：它没有 `82C1C1A0`，却登记了 `82C1C214`。
实际现场 CTR=`82C1C1A0`、LR=`8286FE8C` 与原 caller 相符；旧映射只覆盖比较尾部，
没有执行真实输入的两条链遍历或等值返回路径。

原数据流对两个参数各解引用一个指针，再遍历其 `+32` 链头，节点 `+4` 为 next；
每节点 `+0` 指向被再次读取的 word。函数分别计算 `(word >> 13) & FFFF` 的无符号最大值。
空链最大值为 0；最大值相等返回 0，第一条较大返回 32-bit `FFFFFFFF`，第二条较大返回 1。
这里只描述原指针与整数行为，不赋予未验证的对象/字段名称或原排序库符号。

## Verified：C214 内部尾块引用审计

工具对原 PE **全部非 discardable executable section 的对齐 word** 解码 direct `b/bc` 的目标与 link bit，
同时检查这些代码 word 是否原样等于 C214、所有非代码 section 的对齐大端指针，
以及 executable section 内间隔不超过 96 bytes 的 `lis/addi` 地址构造候选。
最后一种只是语法候选，不声称跨指令寄存器生命周期已证明。

当前精确结果：

- 唯一直接目标引用是 `82C1C208 -> 82C1C214`，link=false，位于完整回调内部。
- 无非代码指针引用，无代码区原始地址 word 匹配，无有界 `lis/addi` 候选。
- 没有观测到独立外部入口证据；这些有界静态结果支持 C214 是内部非等值返回尾块。
  这不是所有运行期计算/间接引用不存在的数学证明，也不扫描 discarded 后缀或任意多指令地址运算。

新严格生成树由完整 0x88 范围自然产生 `sub_82C1C1A0` 和内部 `loc_82C1C214`，
新 mapping 中有完整入口、没有独立 C214 项，未手动删除尾块或编辑生成代码。
验证工具将**完整入口登记与内部 label 存在**作为成功前置守卫；
未来若生成器另保留显式别名则仅记录，不把别名本身强制判错。

## Verified：原 PPC oracle 与真实生成体

有限 oracle 直接读取受守卫的原指令，实现本函数需要的 read/compare/branch/rotate/subfc/subfe/addi/return 子集。
它对未知 opcode、未支持条件、越界或缺失 word、重复完整执行状态（环）和步数超限明确失败；
它不修改输入 memory/registers，不是完整 PPC 模拟器。
另一个独立高层 oracle 仅对输入 word 列表提取 16-bit 字段、求 max、比较大小；两 oracle 的返回必须一致。

14 个夹具覆盖空/空、单空、相等、正负比较、不同链长度、重复最大值、FFFF、7FFF/8000 无符号边界、
高低非字段位噪声。两条原返回路径均被实际覆盖。
XER.CA 和 XER.SO 以不同种子进入；每组核对全部 **32 个 64-bit GPR、LR、CR6 的 LT/GT/EQ/SO、XER.CA**，
以及全部 **4,096 bytes 内存不变**。

特别核验原尾块：第一条较大时 `subfc/subfe` 得到负位模式，随后 `rlwinm` 将值截为低 32-bit，
`addi` 的最终 **r3.u64=`00000000FFFFFFFF`，不是 `FFFFFFFFFFFFFFFF`**；此路径 CA=0。
第二条较大时 r3.u64=1、CA=1。相等路径直接返回 0，保持输入 CA；每次比较的 CR6.SO 来自输入 XER.SO。
因此没有为了“有符号 -1”描述而改写或归一化原 64-bit 寄存器状态。

原样生成体来自 `mc2_probe_recomp.176.cpp:28437`：

- 文件 SHA `fbd119a781fc18c27e76be4bb8a8757aac142a3f20f658341d2a62ba8e86c17e`。
- body SHA `887b1d741a9d6eaea316ae464c95ee7cae9eb80e9c4f2d548e3f355d6b36474e`。

本机 harness 直接编译该完整 body 与 SDK 内存宏，没有 callee、没有替换 dispatch 宏、没有手写游戏回调。
实际 compile exit=0、run exit=0，14/14 用例全部 `success=1`；EXE SHA：
`2b7f5e29bb0c7274973fc47d02315277404c4c6ee2b424fd0ac8a842561fbde3`。
这不是实际游戏对象内容或后续排序结果已验收；这里只证明规定输入上的完整原生成函数与两个独立 oracle 一致。

生成树 400 files、SDK include 1,119 files、Clang resource headers 294 files、compiler、vcvars、
原 XEX/loader/mapping 身份均在实验后重新检查不变。系统 MSVC/Windows 头和链接库未逐文件 hash 覆盖，
不宣称跨机器位级重现。

## 失败保留、测试和复现

添加两个 mapping 前置守卫测试时，一次测试块插入位置错误导致 `IndentationError`，
记录保存在 `compare-tests-mapping-guarded.log`，修复只涉及测试缩进，原测试内容保留。
最终 **15 tests / OK**，包含入口登记缺失和内部 label 缺失两个负例；
测试另明确允许保留尾块显式别名。实际生成体各次编译/运行均成功，旧目录不覆盖。

```powershell
python -m tools.research.verify_compare_callback `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --mapping local/analysis/phase7/thunk-codegen/project/generated/default-disc1/mc2_probe_init.cpp `
  --generated local/analysis/phase8/compare-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' `
  --output local/analysis/phase8/compare-generated-mapping-guarded
python -m unittest discover -s tests -p test_compare_callback.py -v
```

再次运行须使用新的输出目录。省略四个 toolchain 参数只做原指令/引用审计，不标记为生成体执行结果。
最终 `.json` 包含原范围 hash、逐输入 oracle 寄存器/flags/trace、完整引用审计、真实编译命令、
literal/expected 输出和退出码；日志为 `compare-generated-mapping-guarded.log` 与
`compare-tests-mapping-guarded-final.log`。全部原像、生成代码、EXE 与实验报告留在 ignored `local/analysis/phase8/`。

## 原标题继续后的下一实际脚本分派缺口

完整原标题已越过比较回调。18 原成员根随后发现 `GuidCache.xxx` 缺失所致部署失败，
记录保留但不归为生成兼容缺陷。严格新建并验证增加原 GuidCache 的 19 成员根后，
`boot-guidcache/run.txt` 捕获新的 `ctr=82509380`、`lr=8251785C`、
`r3=43F18400`、`r4=7018D210` fatal。

独立原 XEX 守卫核验 `82509380..82509398` 为完整 **24 bytes/6 指令** 的叶函数：

```text
lis r11,8325
lwz r3,8(r4)
addi r10,r11,0980
lwz r9,0118(r10)
mtctr r9
bctr
```

它读取原 frame `+8` 到 r3，再从固定地址 `83250A98` 取下一目标并尾分派，保持 LR。
该固定地址等于另一个表 base=`83250980` 加 slot `46` 的四字节偏移，**不是 GNatives[46]**。
原像该槽为 0，但运行期值尚未捕获；当前原函数尚未执行，不能据原静态零槽断言下一次运行也将调 0。
该叶入口无包含它的 PDATA，也没有当前生成 mapping；前一函数在 `8250937C` 以 `bctr` 结束，
后一标准序言从 `82509398` 开始。原静态指针 `8320B760` 指向此目标。

本次运行保存的 `title-natives.bin` 独立证实：**唯一 GNatives 槽 52 指向 82509380**。
这里 `52` 为十六进制的脚本 token/注册槽，不能直接说成 UFunction 声明的 native index 82。
原 caller `82517844` 读 cursor 所指 byte，`8251784C` 将 cursor 推进一字节，
`82517850` 根据该 byte 乘四读 GNatives，`82517858 bctrl` 建立现场 LR=`8251785C`。
因此当前运行已经到达真实脚本 bytecode 分派，而不是仅在手选 native 夹具中调用。

阶段 4 原报告没有该目标的名称配对，也没有 indexed-initializer 记录。
只读复查发现原因是原注册恢复器把 implementation 限制为“已生成入口”；本目标当时缺失，所以被过滤。
在本地分析中显式把这个已由原边界和实际调用证实的目标加入边界 witness 后，
原精确模板恢复 `82E710C8`：从 `8320B760` 读目标并写 `GNatives[52]`，地址 `83250EC8`，
与实际运行 dump 相符。没有修改恢复器、注册函数、原表或生成代码。

项目 bytecode framing 对 byte `52` 按 ref+expression 处理，但此处不据外部枚举赋予原函数名称或转换语义。
slot 46 的下游表职责需要下一阶段独立验证，不能把两个表的 index 混为一谈。

对这次实际 GNatives dump 的有限差集审计还确认：4,096 槽中 3,794 为 fallback，
非 fallback **302** 槽包含旧 299 条静态初始化记录的全部 index/target，且无不一致；
其余三项为：

|十六进制槽|实际目标|当前生成 mapping|
|---|---|---|
|`01`|`82505A60`|有|
|`52`|`82509380`|无，本次真实阻塞|
|`61`|`82517D70`|无，尚未实际调用验证|

这里没有自动为未调用的槽添加 hint；`01` 未被旧精确模板覆盖的具体原因也尚未调查。
该差集只是实际 dump 对历史列表的比较，不把所有未列入项统一归因为同一种筛选机制。
完整 index/target/mapped 记录与 dump hash 见 `next-blocker-native-gap.json`。

完整原范围 hash、指令、PDATA/mapping、实际日志与 native dump hash、原注册模板和 upstream 见证
保存在 `local/analysis/phase8/next-blocker-initial.json`，窄范围检查日志为 `next-blocker-inspection.txt`。
本阶段只定位该新的真实入口覆盖缺口，不新增 hint、不改原数据或 SDK。
