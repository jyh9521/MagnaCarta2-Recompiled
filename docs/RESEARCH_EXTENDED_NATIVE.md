# 原 GNatives[61] 扩展后缀分派：全部 256 输入差分

## Verified：原版本守卫与实际调用见证

`tools/research/verify_extended_native.py` 只读使用既有原 XEX、pinned loader-source 完整 SHA-256 守卫，
固定以下范围，不修改原文件、标题输入、SDK 或旧生成树：

|范围|长度|证据|
|---|---:|---|
|`82517D70..82517D9C`|44 bytes|完整 11 条原指令，SHA `b628e1746cfef4cd7c8340ad46cddaaf9fe16e6a083111c11983d7e43c6ce471`|
|`82E78008..82E78084`|124 bytes|从原静态槽 `8320BAD4` 注册目标到 GNatives[61]|
|`8250820C..82508230`|36 bytes|原 caller `82508228 bctrl` 与现场 LR=`8250822C`|

61 是十六进制注册槽，而不是额外推定的 UFunction 名称。
原注册目的地址为 `83250F04`；原源指针确为 `82517D70`，无包含该入口的 PDATA。
阶段 9 完整 mapping 受独立固定 hash 守卫，确认旧树没有该入口。
原实际标题调用证据与缺入口经过见 [网关研究](RESEARCH_NATIVE_GATEWAY.md)。

## Verified：字节、游标和扩展槽的精确语义

原函数从 frame `+12` 读取 cursor，取 `BE8[cursor]` 为 suffix，
将 cursor+1 的低 32-bit 大端写回 frame `+12`，然后尾分派：

```text
target = BE32[83251180 + 4*suffix]
       = GNatives[100 + suffix]
```

100 为十六进制，suffix 范围 00..FF，槽范围 100..1FF。
这是**同一 GNatives 表的扩展槽**，不是上一网关的另一张 selector 表。
没有新增调用帧，没有修改 LR；r3/r4/r5 原值保持。
临时寄存器 r6 为 suffix*4、r8 为零扩展 suffix、r9 为 64-bit cursor+1，
r10=`FFFFFFFF83250D80`、r7=`FFFFFFFF83251180`，r11/CTR 为零扩展 target。
原指令没有更新 CR 或 XER；所有条件位和 carry/overflow 状态保持。
这里只给原数据行为，不根据外部枚举赋予原函数或下游名称。

有限 oracle 从受守卫的原 11 words 顺序执行所需 read/add/rotate/write/mtctr/bctr，
只接受精确原模板；未知指令、缺失/非法 byte、越出定义 guest 范围的读取会明确失败。
byte-addressed memory 和寄存器输入先复制，唯一允许写入的是 frame `+12` 四字节。
单元测试还核验 cursor=`FFFFFFFF` 时 r9=`0000000100000000`、写回 word=0；
这是 oracle 边界测试，不冒称该额外边界已在真实标题执行。

## Verified：真实新生成体、256/256 suffix

原样新生成体位于 `mc2_probe_recomp.102.cpp:6719`：

- 文件 SHA `07e661f35bf4efe11d72cf02491dfe84b02297a130540253613338dc0c43142c`。
- body SHA `d2bde882db5d6f65a5013bc4f922105ba276d2aca94978e8580c52a6357a59e0`。

验证要求唯一完整 body，image mapping 和 `registrar->SetFunction` 各恰一次、同地址同 `sub_82517D70`；
缺登记、重复或错符号均拒绝。生成函数、PPCContext、SDK 加载/存储宏不改；
**仅把未知外部 `REX_CALL_INDIRECT_FUNC` 边界替换为记录目标，不执行任何未知 callee**。

harness 是独立进程中的**纯合成稀疏内存实验**，没有加载 XEX、没有标题入口、没有原静态数据，
也没有修改真实标题 GNatives。它预留 4 GiB，只 commit 四页/16 KiB，分别用于两个交替低/高 frame、
suffix 脚本 byte 与合成后缀 dispatch 槽。
这里的同地址 suffix 表只是 oracle 输入，不是给标题提供的伪造 GNatives 或原数据替代品。
高 guest 页使用原 `REX_PHYS_HOST_OFFSET` 公式 commit/snapshot，不改变原 SDK 宏。

所有 00..FF suffix 逐一执行，每例检查：

- 全部 **32 个 64-bit GPR、CTR、64-bit LR** 对应原 word oracle。
- CR0..CR7 的全部四位与 XER.CA/SO/OV 保持种子值。
- 全部四页内存仅出现 frame `+12` 的 cursor+1 大端 word 改动，script 和 dispatch 槽保持。
- 未知目标只记录，包括 0、FFFFFFFF、正常高位地址；最终四页及预留地址全部释放。

实际 compile exit=0、run exit=0，257 行原始输出（256 个用例加清理）中每例均 `success=1`：

```text
EXTENDED_CASE 0 suffix=00 target=00000000 cursor_delta=1 success=1
EXTENDED_CASE 1 suffix=01 target=82000100 cursor_delta=1 success=1
...
EXTENDED_CASE 254 suffix=FE target=8200FE00 cursor_delta=1 success=1
EXTENDED_CASE 255 suffix=FF target=FFFFFFFF cursor_delta=1 success=1
EXTENDED_MEMORY pages=4 released=1
```

完整逐字输出在本地报告与 `run.txt`，上例省略中间重复行，仅用于概览。
EXE SHA `cfbf578bbce3d84a0379ee2472d986b529910c8d91bae87e2dbddcf0b1bd8a2a`。
本实验不读取或推断真实原标题下一 suffix，不把“全部后缀在合成夹具正确分派”说成实际下游函数均执行成功。

原 XEX/loader/mapping、生成树 400 files、SDK include 1,119 files、Clang resource headers 294 files、
compiler 与 vcvars 运行后 hash 全部不变；MSVC/Windows 系统头/库未逐文件 hash 覆盖，不宣称跨机器位级重现。

## 测试、失败记录与复现

```powershell
python -m tools.research.verify_extended_native `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --mapping local/analysis/phase9/gateway-codegen/project/generated/default-disc1/mc2_probe_init.cpp `
  --generated local/analysis/phase10/extended-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' `
  --output local/analysis/phase10/extended-generated-first
python -m unittest discover -s tests -p test_extended_native.py -v
```

输出目录必须不存在，重跑选择新名称。省略四个 toolchain 参数只做静态与有限 oracle 验证，
不会冒称执行生成函数。公开 **11 tests / OK**，包括全部 256 suffix 的独立语义检查、
每条 opcode 篡改拒绝、byte 边界/无效值、游标回绕、唯一 body/metadata 与稀疏页映射/清理。
本子实验的首次静态、单元测试、编译和实际执行均通过；没有制造额外失败记录。
`extended-static-first/`、`extended-generated-first/`、`extended-tests-first.log` 原样保留，
其中 `.json` 包含全部输入、逐 case oracle 状态、实际命令、literal/expected 输出、退出码及 hash。
完整原像、生成代码、harness 和 EXE 仅在 ignored `local/analysis/phase10/`。
