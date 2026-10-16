# GNatives[52] 到另一 selector 表的原始网关

## Verified：固定原范围与两个不同分派表

`tools/research/verify_native_gateway.py` 复用原 XEX 和 pinned Xenia loader-source SHA-256 守卫，
只读展开原像并固定三个完整指令见证：

|范围|长度|作用|
|---|---:|---|
|`82509380..82509398`|24 bytes|六指令 tail-dispatch 网关|
|`82E710C8..82E71144`|124 bytes|原 GNatives 槽 52 注册模板|
|`82517828..8251785C`|52 bytes|原 cursor 取 byte 后间接调用网关的 caller|

网关范围 SHA-256 是 `24858452f74ebfe37c65055b81249f2b52a972d7f8374451f2b260775436bad2`，
无包含它的 PDATA。原指令分别读取 frame `+8` 与固定 selector 地址：

```text
lis r11,8325
lwz r3,8(r4)
addi r10,r11,0980
lwz r9,0118(r10)
mtctr r9
bctr
```

最终 r3 为 frame `+8` 的零扩展 word；r11=`FFFFFFFF83250000`，
r10=`FFFFFFFF83250980`，r9 和 CTR 为 `BE32[83250A98]` 的零扩展 word，LR 保持。
读取的有效地址按低 32-bit 计算。它不写内存、不修改 frame cursor，也不验证目标是否可执行。

原 `82E710C8` 从静态槽 `8320B760` 取得 `82509380` 并写入 `GNatives[52]`，
地址 `83250EC8`；槽 52 为十六进制。原 caller `82517844` 取 byte，
`8251784C` 先推进 cursor 一字节，`82517858 bctrl` 建立已观测 LR=`8251785C`。

**GNatives[52] 与网关要读取的 selector 表不是同一张表**：
后者 base=`83250980`、slot=`46`、地址=`83250A98`。本实验不将其改称 GNatives[46]，
不根据外部枚举给网关或下游函数命名。阶段 8 已捕获真实 GNatives[52]→网关的调用；
本节合成实验本身不装载游戏，不把原像中 selector 静态零槽当成真实运行期目标。

## Verified：原样新生成体的稀疏内存差分

新严格生成的完整 body 位于 `mc2_probe_recomp.9.cpp:6436`：

- 文件 SHA `db16bc445d60ea0bd3af67d865c61ddcbaa4034664790442582e05bbb2d4360d`。
- body SHA `7376022bb910657fde8eda9b6fdfdc9a495def0fee088d17020badce71f1833f`。

验证工具要求唯一完整 body，并把 image mapping 与 `registrar->SetFunction` 各恰好一次、
同地址同 `sub_82509380` 符号作为成功前置守卫，拒绝缺项、重复、错符号以及未知 shape、store 或 fatal。
独立有限 oracle 只接受受守卫的六条指令模板；缺失 word、非法 word 或未知指令直接失败。
oracle 记录未知外部目标，不调用它。

独立本机 harness 使用 Windows `VirtualAlloc` 预留 4 GiB 虚拟地址，但只 commit **5 页/20 KiB**。
这些页只是四个合成 frame 和 selector 地址的合成存储；没有 `LoadXexImage`，没有原数据段，
没有原 vtable，没有 GNatives 初始化，也没有原标题入口输入夹具。
selector 所在页虽然在同一数值范围内包含 GNatives 起始地址，harness 明确不写 `+B00` 之后的页区间，
因此 GNatives 数值地址区间保持系统零页，既不填原槽也不伪造注册。

生成函数体、PPCContext 和 SDK load/store 宏原样使用；**只将未知外部 `REX_CALL_INDIRECT_FUNC`
边界替换成记录目标**，不执行目标 callee。
四例涵盖零、全一、高位、正常值，包括高 32-bit 非零的 r4 和高 guest frame 地址。
逐例检查全部 **32 个 64-bit GPR、CTR、64-bit LR、全部 5 个已 commit 页的内存不变**。
因此 r3/r9 的零扩展、r10/r11 的符号扩展不是只检查低 word 的近似验证。

实际 compile exit=0、run exit=0，逐字输出：

```text
GATEWAY_CASE 0 object=00000000 target=00000000 unchanged=1 success=1
GATEWAY_CASE 1 object=FFFFFFFF target=FFFFFFFF unchanged=1 success=1
GATEWAY_CASE 2 object=12345678 target=8250BAF0 unchanged=1 success=1
GATEWAY_CASE 3 object=80000000 target=80000000 unchanged=1 success=1
GATEWAY_MEMORY pages=5 released=1
```

EXE SHA 为 `020fcefa956a31fa8bf376d40446147b963cb9876455c3efc00fbfd5b67a84a6`。
预留空间最终明确释放；本结果不证明零、全一或任何记录目标可在真实标题中调用。
生成树 400 files、SDK include 1,119 files、Clang resource headers 294 files、compiler、vcvars
和原输入在运行后重新核对 hash 不变。系统 MSVC/Windows 头/库不在逐文件 hash 覆盖内，
不宣称跨机器位级重现。

## 真实失败保留与纠正

第一次 harness 编译成功但执行 exit=`C0000005`（3221225477），记录在 `gateway-generated-first/`。
原因是原生成 Windows SDK 宏对 guest 地址 `>=E0000000` 加 `REX_PHYS_HOST_OFFSET=1000`：
高 guest frame `FFFEE000` 的实际 host 页是 `FFFEF000`，初版只 commit 前者。
这是一道**合成 harness 页映射错误**，不是游戏、SDK 或原网关函数缺陷。
修复只使 commit/snapshot 页使用原宏同一公式；没有修改宏、函数体或 guest 指令。
相关证明保存为 `gateway-first-failure-analysis.json`，新增测试要求页选择显式采用原宏。
随后 `gateway-generated-final/` 四例通过；增加一对一 metadata 守卫后，
最终 `gateway-generated-registered/` 四例仍通过，首次失败目录不覆盖。

## 复现与公开测试

```powershell
python -m tools.research.verify_native_gateway `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --mapping local/analysis/phase8/compare-codegen/project/generated/default-disc1/mc2_probe_init.cpp `
  --generated local/analysis/phase9/gateway-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' `
  --output local/analysis/phase9/gateway-generated-registered
python -m unittest discover -s tests -p test_native_gateway.py -v
```

复跑选不存在的新目录；省略四个 toolchain 参数只执行原静态/有限 oracle 检查。
公开合成测试 **12 tests / OK**，涵盖六指令逐条拒绝、有限 word 边界、64-bit 状态、
未知目标不执行、缺 mapping/body、重复 body、缺失/重复/错符号登记、稀疏页映射及释放。
实际日志为 `gateway-generated-registered.log`、`gateway-tests-registered.log`；完整命令、逐字输出、
退出码及输入身份保存在 `gateway-generated-registered/gateway-verification.json`。
原像、生成体、harness、EXE 与报告均在 ignored `local/analysis/phase9/`，不提交游戏资产。

## 真实标题越过网关后的下一分派入口缺口

新完整原标题已越过 GNatives[52]→`82509380`。
19 成员根随后缺少原 `TitleMap_MSPT.xxx` 导致的部署失败保留，不归为网关兼容缺陷。
严格新建并验证加入原 TitleMap 的 20 成员根后，`boot-titlemap/run.txt` 捕获
`ctr=82517D70`、`lr=8250822C`、`r3=438BC400`、`r4=7018BEB0`，调用路径仍包含原标题入口/main。

独立原 XEX 守卫核验 `82517D70..82517D9C` 为完整 **44 bytes（0x2C）/11 条原指令**，SHA：
`b628e1746cfef4cd7c8340ad46cddaaf9fe16e6a083111c11983d7e43c6ce471`。
无包含它的 PDATA，也没有当前生成 mapping。前一段在 `82517D6C` 以 `bctr` 结束；
本段在 `82517D98` 以 `bctr` 结束，`82517D9C` 是零 padding，下一已生成函数从 `82517DA0` 开始。

实际保存的 4,096 槽 GNatives dump 中，唯一 **61** 槽指向该入口（61 为十六进制）。
原静态槽 `8320BAD4` 同样指向该目标；只读精确模板恢复原注册函数 `82E78008`，
其写入地址 `83250F04` 正是 `GNatives[61]`。
原 caller `82508210` 读取当前 byte，`82508218` 推进一次 cursor，
`82508228 bctrl` 的 LR=`8250822C` 与现场一致。

这个新目标自身的静态行为是：读取 frame `+12` 的 cursor，读取**下一 byte**，
把 cursor+1 写回 frame `+12`，再保持 LR 尾分派到
`BE32[83251180+4*byte]`，即 **GNatives[100+byte]**（100 为十六进制）。
byte 范围 00..FF，因此这是同一 GNatives 表的 100..1FF 槽，不是前节另一张 selector 表。
这里只给原地址和整数行为，不赋予外部枚举中的符号名。

**82517D70 本身尚未执行**：本次运行在找不到该 generated entry 时停止。
所以它将读取的下一 byte、实际扩展槽和下游目标均尚未由运行观察确定；
不能用 caller 刚消费的 61、某段包文本或原静态槽去代替这次未知读取。
完整原范围 hash、原指令、PDATA/mapping、原注册、真实 dump/caller 日志身份
保存为 `next-blocker-initial.json`，窄范围日志 `next-blocker-inspection.txt`。
本阶段不新增 61 的 hint、不改工具、生成树、SDK 或原数据绕过该入口缺口。
