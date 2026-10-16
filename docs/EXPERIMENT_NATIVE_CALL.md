# 真实生成 native 调用最小实验

## Verified：执行路径

本实验使用[完整宿主链接实验](EXPERIMENT_HOST_LINK.md)的全部 **197 个真实 COFF object**，
官方 ReXGlue v0.10.0 runtime 和完整的 58,408 项函数映射。
`src/host/native_add_probe.cpp` 仅准备受控 guest 内存和验收条件，
不抽取/改写游戏函数体，不替换 `REX_CALL_INDIRECT_FUNC`，不提供 native 或 operand decoder stub。

调用链为：

```text
重现原版静态 vtable 两个指针数据项
  → 真实初始化器 sub_82E707C8 和 sub_82E73108 写入 GNatives
  → GNatives[146] 读取真实 guest 地址
  → SDK FunctionDispatcher::GetFunction(0x8250BAF0)
  → 真实生成 sub_8250BAF0 / UObject::execAdd_IntInt
  → 原始生成代码的两次 GNatives[0x1D] 间接分派
  → 真实生成 sub_82508E60 四字节操作数读取
  → 原始加法、结果写回、寄存器恢复和返回
```

**Verified**：hash-locked XEX 中 `0x82157100` 是 UTF-16BE 名称
`intUObjectexecAdd_IntInt`，`0x8320F1E8` 是其 `(name pointer, implementation pointer)`
配对，implementation 为 `0x8250BAF0`。原版 Core 包中 `Object.Add_IntInt` 的 native index 为 146。
`0x82508E60..0x82508EA0` 的真实 PPC SHA-256 为
`bead6bd612e03adfd486b56117ba78183689901cf6ce08bbba67131b1ac6fcab`；
它实际从 `FFrame.Code` 读取四字节、推进指针 4 字节并写入结果。
原版 vtable 的 `0x8320B718`、`0x8320B728` 两处也含该函数指针。

**Verified**：最终实验执行真实生成的 `sub_82E707C8` 和 `sub_82E73108`，
分别读取原版 vtable 的 `0x8320B718`、`0x8320B828`，写入 `GNatives[0x1D]` 和 `GNatives[146]`。
首次真实初始化循环填充全部 4,096 项为 `0x82505980` fallback，并设置 guard `0x8327B660=1`；
第二个初始化器通过 guard 保留第一项注册，最终恰好 4,094 个 fallback、两项真实注册。
再次执行第一个初始化器，原始重复注册路径写入 `0x83263F1C=29`，两项注册保持正确。
本实验**不再手工写入任何 GNatives 槽**，仅重现已从原版 XEX 验证的两个静态 vtable 数据字。
GNatives 位于 `0x83250D80`，由实际 Add 生成代码的地址构造和读取方式确定，
而不是把 UObject vtable 误当作该表。两段原初始化器的 124 字节 PPC 身份分别固定为：

- `82E707C8`：`0f22ced9d1cba6d21c397df528b2ec54899a946468b5fff98efdad68aa92219a`
- `82E73108`：`b253452ee0b71cf128edacfd7908079c79026590b4d21f7e851605688b48f4ee`

完整 CRT/global constructor 链仍未执行；两个初始化器的可执行证据不外推为完整游戏 startup。

## 最小内存与验收

SDK `tool_mode=true` 初始化后不加载完整 XEX image、不启动 guest entrypoint。
探针通过 SDK heap API 单独分配 `0x83250000` 起的 192 KiB 区域以容纳 GNatives、guard、重复注册状态，
并分配 `0x83200000` 的 64 KiB 页以重现两个原始 vtable 数据项，
通过 `SystemHeapAlloc` 分配 64 KiB 的 frame、脚本、结果和 stack；最后释放全部三个分配区。
`FFrame.Context=0`，该测试所经 operand handler 不解引用 UObject。
`FFrame.Code` 位于 frame+12。输入脚本为：

```text
1D <lhs 四字节 BE> 1D <rhs 四字节 BE> 16 53
```

真实 Add 消耗两个 token、两个四字节整数、一个 `EndFunctionParms`，
返回时 Code 精确推进 **11** 字节，留在 `0x53`。没有走可选 `0x41` DebugInfo 路径。
八组输入包含 `7+35`、零、负数位模式、正负边界和 32 位回绕；
独立宿主无符号加法仅用于计算 oracle，不替代被测生成函数。
每组检查结果的 BE 位模式、Code 推进、R1/LR/r28–r31 恢复、结果前后 canary、脚本原字节未变。
`0x7FFFFFFF+1 → 0x80000000`、`0x80000000+0x80000000 → 0` 均实际通过。

## 重现

先按宿主链接文档构建 `--probe-source src/host/native_add_probe.cpp` 版本，
再在项目根目录执行（输出目录必须不存在）：

```powershell
python -m tools.research.probe_native_call --host-dir local/analysis/phase4/host-native-initialized --sdk local/upstream/rexglue/sdk/win-amd64 --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --ufunction-report local/analysis/phase3/native-gap-disc1.json --output local/analysis/phase4/native-probe-initialized
python -m unittest discover -s tests -p test_probe_native_call.py -v
```

工具先验证原版 XEX/loader hash、名称配对、operand PPC hash、vtable 引用和 UFunction 声明。
它在运行前后复验宿主全部已记录输入（197 object、编译器、链接器、两个宿主源）、
SDK 全树、Clang resource include、generated 全树、宿主 EXE hash。
运行时通过实际 `RUNTIME_DLL` 输出验证所载 DLL 路径。
系统 MSVC/Windows SDK 依赖的哈希覆盖边界仍与宿主构建文档一致。

公开测试使用自制数据，不包含商业游戏内容；**16 tests / OK**，覆盖真实输出格式、
回绕 oracle、结果/Code/寄存器/canary/释放失败拒绝、生命周期缺失/重复、名称/实现/hash/references
拒绝、原始初始化器 hash 和 fill/guard/重复注册状态拒绝、声明身份、源/EXE/SDK/其他输入漂移拒绝以及超时/进程启动错误日志保留。
超时和启动失败分别记录 exit=124、127，而不是把启动失败当成 native 执行证据。

## 本地执行证据

- `local/analysis/phase4/host-native-first/`：首次真实集成，8 cases 通过，保留不覆盖。
- `local/analysis/phase4/host-native-validated/`：输入覆盖增强后的完整宿主，保留不覆盖。
- `local/analysis/phase4/host-native-profiled/`：锁定支持版本 generated 树但仍用受控 binding 的中间轮次，保留。
- `local/analysis/phase4/host-native-initialized/`：最终真实初始化器+全模块宿主、输入 hash、链接 map、真实 DLL 路径及日志。
- `local/analysis/phase4/native-probe-final/`：首次独立证据交叉核验及重跑，exit=0。
- `local/analysis/phase4/native-probe-verified/`：加强 SDK/resource/generated 树和 DLL 路径校验后的重跑。
- `local/analysis/phase4/native-probe-inputs-verified/`：运行前后输入复验的中间轮次，保留不覆盖。
- `local/analysis/phase4/native-probe-validated/`：固定 generated profile、运行前后输入复验的中间受控 binding 轮次。
- `local/analysis/phase4/native-probe-initialized/`：最终原初始化器证据交叉核验及独立重跑，`native-call.json` / `run.txt`。
- `local/analysis/phase4/native-probe-initialized-tests.log`：16 项公开单测原始日志；前版 15 项日志继续保留。

最终真实输出：

```text
NATIVE_INITIALIZERS operand=82E707C8 add=82E73108 guard=1 fallback_slots=4094 duplicate_index=29 success=1
NATIVE_ADD cases=8 index=146 target=8250BAF0 operand=82508E60 fixture_released=1 status=0
NATIVE_PROBE status=0
SHUTDOWN complete
NATIVE_CALL cases=8 full_module_objects=197 exit=0 success=True
```

宿主 EXE SHA-256：`a1f64f864ed6b8ece37762f98d94e8e5746a2b071ff300ec2d92092a61057355`。
不同绝对路径或工具链不保证生成相同 EXE；构建应记录实际身份，不能只比照本次 hash。

## 失败认识与边界

早期把 `0x8320B5E0` 的 UObject vtable 误判为 GNatives 初始表，
整数运算的一段顺序偶合造成 index 146 看似吻合，但所谓 token `0x1D` 的函数
`0x82505AF8` 会走 UObject/属性解析，绝非简单 IntConst；该猜测在执行前已撤回。
这不是一个失败的 native 执行，不能把错误表解释写成原始 opcode 初始化发现。
相关失败调查继续由 native 名称注册研究保留；上面的每一轮真实执行目录均独立保留。

本次验证两个真实原始注册初始化器、一个真实 native 算术实现和一个真实 operand handler 可执行并返回，
不表示 3,056 个 native 都可用，也不表示路线 B VM 已实现，
不证明 UObject、UProperty、动态名称调用、异常、GPU、游戏启动或首帧。
后续应推进完整 startup constructor 链、完整 Script VM 调度和真实对象环境。
