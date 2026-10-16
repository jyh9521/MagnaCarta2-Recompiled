# Native 名称表、索引注册与真实入口（第四阶段）

## Verified：输入与复现边界

`tools/research/native_registration.py` 只读分析第一盘已验证 XEX，并分别与两盘第三阶段 UFunction 报告连接。XEX SHA-256 由现有解码入口固定；Xenia loader source 也固定 SHA，密钥只在内存中派生，不输出密钥或完整镜像。UFunction 报告 SHA-256 固定为 `e85657c5262ecae241960f91bbe2d883bf0d58bac4a858d76581d02346087714`，生成模块注册文件固定为 `64e962b32141dacc7236876a62101d391599e21cabde78fb538ecc4815979669`。空、部分、修改过的报告或注册文件在解码前拒绝，不能产生“零函数成功”。

两盘报告内容本身相同，本轮双次解析的汇总、逐声明候选与 initializer 清单也相同。它们共享同一已验证执行镜像，不把双盘数量相加。CLI 在结束时重新计算全部输入哈希，并拒绝输出别名或硬链接覆盖输入。

```powershell
python -m unittest discover -s tests -p test_native_registration.py -v
python -m tools.research.native_registration --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --ufunction-report local/analysis/phase3/native-gap-disc1.json --generated-register local/analysis/phase3/branches-bounded/project/generated/default-disc1/mc2_probe_register.cpp --output local/analysis/phase4/native-registration-disc1-final.json
python -m tools.research.native_registration --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --ufunction-report local/analysis/phase3/native-gap-disc2.json --generated-register local/analysis/phase3/branches-bounded/project/generated/default-disc1/mc2_probe_register.cpp --output local/analysis/phase4/native-registration-disc2-final.json
```

## Verified：不是单纯字符串搜索

原镜像包含完整 UTF-16BE 名称，例如 `intUObjectexecAdd_IntInt`。恢复工具要求：

1. 名称四周的编码与 NUL 边界有效，匹配完整 `int` + `U/A` class + `exec` + source function identifier，不用 FriendlyName 运算符代替源标识符。
2. 大端四字节对齐记录确实保存 `{name_pointer, implementation_pointer}`。
3. implementation 必须恰好属于 SHA 锁定生成注册文件的真实函数入口集合，而不只是“位于代码地址范围”。
4. 同类记录以八字节步长连续，并具有 `{0,0}` 终止记录。缺终止或边界不明的记录留在未接受清单，不升格为映射。
5. Core 表还有独立指令消费者证据：`0x823C7F40` 实际构造表地址 `0x8320EC20`，比较完整名称，按 `index * 8` 遍历，命中时返回 `table + index * 8 + 4`。**它返回 implementation slot 的地址，不是一次 native 执行。** 工具验证关键 PPC 指令并保存完整检查区间 SHA。

已恢复 **312 个静态表、2,676 个非零 name→entry 记录**。Core 主表范围 `0x8320EC20..0x8320F288`，205 项；Add 的真实记录为 `0x8320F1E8`，名称指针 `0x82157100`，实现入口 **`0x8250BAF0`**。

默认名称扫描拒绝其他字符串内部的 `intU...` 后缀。三处编译器打包的首字面量紧随非字符串数据，前面没有 NUL；仅对此固定 XEX 的 `0x820C2030`、`0x821517C0`、`0x82156C20` 显式放行，通用默认不放宽。每项例外仍需要真实指针记录、有效代码入口及完整表结构支持。

## Verified：3056 个声明的静态绑定缺口

|包|唯一非零 name entry|静态 name slot 为零|没有静态 entry|
|---|---:|---:|---:|
|Core|207|0|0|
|Engine|858|213|15|
|IpDrv|8|0|0|
|MC2Game|1601|50|0|
|OnlineSubsystemLive|0|97|0|
|UnrealScriptTest|2|4|1|
|合计|2676|364|16|

364 项只证明静态镜像中相应名称后面的 slot 为零，**不等于函数永远不存在**；动态初始化、成员指针表示及注册过程仍需分别恢复。16 项主要属于接口声明，不能把没有静态表当作丢失实现的充分证据。

表名没有 package 字段，UFunction 也没有 C++ `U/A` 前缀字段，所以输出明确保留这两种未证明关系。相同 class.function 跨包出现或候选 `U/A` 混合时，工具输出歧义状态，不把它们都标成唯一绑定。当前真实数据没有这些冲突；唯一静态名称候选不代表兼容引擎调用已经闭包。

## Verified：GNatives 注册 initializer

真正动态分发表为 **`0x83250D80`，4096 个四字节入口**。工具在真实函数入口处恢复 **299 个严格匹配的注册 ctor**：完整 31 条指令模板逐项检查，允许的变项仅为 index、源 pointer slot 及对应高/低地址。它验证两条分支的 source slot 一致、目的 slot 恰好为 `GNatives + index * 4`、源 slot 里确实存在真实函数入口；没有运行宽松的未知 PPC 模拟器。

首次 ctor 检查 `0x8327B660` flag，把全部 4096 项填为 fallback `0x82505980`，随后读取原镜像中的指针槽并注册本项。后续 ctor 保留先前注册；若目的 slot 已不是 fallback，原逻辑还把重复 index 写入 `0x83263F1C`。这段原始逻辑不是工具自行合成的注册表。

|用途|真实 initializer|源 pointer slot|实现入口|GNatives index|
|---|---|---|---|---:|
|IntConst operand handler|`0x82E707C8`|`0x8320B718`|`0x82508E60`|29 / `0x1D`|
|Object.Add_IntInt|`0x82E73108`|`0x8320B828`|`0x8250BAF0`|146 / `0x92`|

**203/203 个非零 native index 的 UFunction 声明均同时匹配静态名称 entry、实现入口和对应 initializer 的 index。** 其余 96 个 ctor 含字节码处理入口等项目，不能把 299 全部当成 UFunction 声明数量。索引为零的 2,853 个声明仍需名称查找/注册，不套用 `GNatives[0]`。

静态工具的输出仍标注 `runtime_registration=not-executed`。真实 ctor 和 Add 的运行结果由独立宿主调用实验记录；本工具不以静态存在替代运行证明。该重编译入口也不等于路线 B 已有 2,676 个可独立使用的 PC native 实现。

## ABI 与最小调用选择

Add 使用 PPC `r3=UObject/Context`、`r4=FFrame*`、`r5=Result*`。它读取 frame+8 的 context、frame+12 的 Code，按操作数字节查 GNatives 调用，最终向 Result 写入整数和，推进 Code 越过参数结束标记。`0x82508E60` 从 Code 读取四字节整数，Code 前进四字节并写 Result。除数、对象生命周期、属性系统、栈布局和任意其他 native ABI 没有由此自动得到验证。

最小实验应先执行上述两个**原始生成 initializer**，再以真实 `IntConst(参数1), IntConst(参数2), EndFunctionParms` 输入运行原始 Add。输入、UObject/FFrame、结果槽及宿主内存属于受控 fixture；算术 handler、操作数 handler、分发表初始化逻辑来自真实生成代码。它不是完整 VM、游戏启动、地图加载或路线 B 的替代实现。

## 失败与反证保留

- 最初误把 `0x8320B5E0` 看作 GNatives 初始数组。独立交叉核对发现只有 **33/203** 项碰巧一致，token 0x1D 的该位置还访问 UObject flags；这是 **UObject vtable**。完整反证和错误候选保存在 `local/analysis/phase4/native-registration-failures.json`。随后真实 ctor 证明应读取不同 vtable slot，再写动态 GNatives，而不是把 opcode 当作 vtable index。
- 第一版 Core 指令 witness 的循环指令位置差一条，工具明确报错；`native-registration-first.log` 保留，修正后按真实指令序列通过。
- 默认要求字面量前有 NUL 一度漏掉三处首字面量，暂只映射 2458 项；`native-registration-disc1.json` 保留。仅对固定镜像的三处已验证起点增加例外，并保留普通后缀拒绝测试。
- 独立审查用空 UFunction 报告复现“native0但成功”的错误；`native-registration-empty-audit.json` 保留。加入完整报告和生成注册文件 SHA 守卫后，同一输入明确失败，`native-registration-empty-audit-rejected.log` 保留。
- 本地逐名称记录、完整 initializer 清单、源指针及调用报告不提交。仓库只保存通用只读工具、自制测试和聚合结论；原 XEX、生成模块、SDK、密钥和完整游戏资源不进入 Git。
