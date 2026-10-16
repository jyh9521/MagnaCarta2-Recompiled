# UFunction/native 与字节码调用缺口（第三阶段）

## Verified：真实数据范围

只读工具 `tools/formats/ufunction.py` 按两盘第一阶段成员 SHA-256 定位并验证七个定义包，再按逻辑区间读取 payload。每盘 12,901 个 Function 的字段、序列化边界、引用区间及字节码 token framing 全部通过；字节码共 1,287,577 字节。两盘七包 hash、逐函数元数据/调用边和统计完全相同，不能把双盘数量相加。

|包|函数|FUNC_Native|非零 native index|零 index native|
|---|---:|---:|---:|---:|
|Core|241|207|153|54|
|Engine|3,565|1,086|50|1,036|
|GameFramework|1|0|0|0|
|IpDrv|50|8|0|8|
|MC2Game|8,715|1,651|0|1,651|
|OnlineSubsystemLive|239|97|0|97|
|UnrealScriptTest|90|7|0|7|
|合计|12,901|3,056|203|2,853|

**native index=0 不等于脚本实现。** FUNC_Native 标志仍要求原生实现/注册；MC2Game 的 1,651 项全属于此类。3,056 项是声明数量，不是已恢复 C++ 实现数。兼容 PC native 实现本轮验证数为 0。

## Verified：446/25 序列化边界

此 UFunction profile 仅支持 Xbox 大端 446/25；实际分析入口明确拒绝同版本小端包。预期七个定义包若任一无 Function export，也明确失败，避免空数据被当作成功。两项真实入口链的自制 fixture 回归已加入，当前 UFunction 测试合计 46 项通过。

本样本虽然在 CookedXenon，仍保留 ScriptText/CppText/Line/TextPos/FriendlyName。不能直接套用“console cooked 必定剥离这些字段”。整数大端，FName 是两个 u32，object reference 是有符号 i32。

|相对 payload 偏移|字段|
|---:|---|
|0|NetIndex i32|
|4|属性流终止 FName(None)，本批所有 Function 都为空属性流|
|12,16|UField Super、Next 引用|
|20,24,28|UStruct ScriptText、Children、CppText 引用|
|32,36|Line、TextPos i32|
|40|ScriptSize u32|
|44|ScriptSize 字节 bytecode|
|44+ScriptSize|NativeIndex u16、OperPrecedence u8、FunctionFlags u32|
|后续|若 flags & 0x40，RepOffset u16；末尾 FriendlyName FName|

非网络函数总大小是 59+ScriptSize；网络函数多 2 字节。所有函数精确耗尽 export serial_size，没有猜测尾部/魔数搜索。断言非零 index 必须同时有 FUNC_Native(0x400)。每个函数记录包 hash、export index、serial offset/size、payload/script hash、fields 和调用偏移，留本地审计。

LZX 只解压命中区间的块，4 块 LRU；不构造完整逻辑包内存镜像。输入只读，输出 JSON 原子替换，拒绝覆盖输入或硬链接。

## Verified：token framing 与调用边

|调用形式|静态调用点|
|---|---:|
|直接 native-index / extended native|26,117|
|FinalFunction object reference|8,375|
|VirtualFunction FName|13,683|
|GlobalFunction FName|10|
|DelegateFunction|38|

26,117 个直接 native 调用点均能匹配 203 个非零 index 声明中的一个；`unresolved-native-registration=0` 仅指这些静态调用点，不证明注册表/实现已经恢复。FinalFunction 中 6,345 个指向 native 声明、2,030 个指向脚本声明；通过本包 export 或七包 import 全路径匹配，没有未匹配 final 目标。virtual/global/delegate 保留动态绑定，未标为运行时闭包。

解析器递归处理表达式和参数边界，操作数中的 native 字节不会被扫描误计；拒绝未知 token、越界引用/名称、截断、缺 EndOfScript、错误参数/默认参数终止、深度超过 128。只验证序列化 framing 和静态引用，不执行字节码，不验证跳转目标/栈类型/全部控制流语义，不生成脚本源码。未出现 token 的支持分支仅由自制测试/上游格式依据支持，不能称真实数据覆盖。

## 失败记录（保留）

1. 首次实际解析：12,900 通过、1 个 UnrealScriptTest 函数出现 `unterminated call parameter list`。原因是误给 ArrayFind 446 profile 加了 EndFunctionParms；开源对照中的追加门槛是 649。修复后全通过。原报告 `local/analysis/phase3/native-gap-disc1-first.json` 保留。
2. 加严表达式 delimiter 检查后：12,897 通过、4 个 delegate comparison 被误拒。该操作本来需要独立 EndFunctionParms，不能当普通第三表达式。专门验证终止 token 后恢复全通过；失败报告 `local/analysis/phase3/native-gap-disc1-delimiter-failure.json` 保留。
3. 上游文件第一次按宿主 cp932 读取报 UnicodeDecodeError；随后显式 utf-8-sig。未用替换解码掩盖错误。
4. 独立审查发现顶层孤立 EndFunctionParms/EndParmValue 曾被接受。自制 `16 53`、`15 53` 复现后，顶层明确拒绝这两类 delimiter；新增两项回归，44 项 UFunction 测试全部通过。重跑双盘仍各 12,901 函数通过，真实调用计数不变。

## 固定开源交叉核对

[EliotVU/Unreal-Library](https://github.com/EliotVU/Unreal-Library/tree/d13f344007396620bdfc922db1790ff338045804)，固定 commit `d13f344007396620bdfc922db1790ff338045804`，MIT。参考 UObject/UField/UStruct/UFunction、DefaultEngineBranch、PackageObjectLegacyVersion 和各 token 类的字段顺序/版本门槛；Python 工具独立实现，不复制代码。未使用商业 UE3 源码。上游原文件、完整逐文件 SHA-256 清单只留 local；关键对照：

- UStruct.cs SHA-256 `8d77d0fe8daed93253f89f7ed9ea8376eceb254cf67babbb90702ed1d0c5604b`
- UFunction.cs SHA-256 `6e943cd0adab25d6a4541b2a2c5a6e056798bbdf7d3bfb2c4dead7bcfc230c95`
- DefaultEngineBranch.cs SHA-256 `9a277cc8e17b3b58bd0c80690e5a89ea55b1046ec5cf7cdff399a33d366d0b59`

## 复现

```powershell
python -m unittest discover -s tests -p test_ufunction.py -v
python tools/formats/ufunction.py 'MagnaCarta II (Korea) (Disc 1).iso' local/analysis/phase1/disc1.json --lzx-library local/analysis/phase2/ue3_lzx.dll --output local/analysis/phase3/native-gap-disc1.json
python tools/formats/ufunction.py 'MagnaCarta II (Korea) (Disc 2).iso' local/analysis/phase1/disc2.json --lzx-library local/analysis/phase2/ue3_lzx.dll --output local/analysis/phase3/native-gap-disc2.json
```

本地 native-gap.json 汇总双盘一致性、包身份、native 分组、失败记录及固定上游 SHA。逐函数报告不提交；只提交通用工具、自制 fixture 测试和聚合知识。路线 A 保留原始 PPC native 逻辑的重编译路径，与路线 B 重新实现 native 语义不是同一个缺口。

下一门槛是恢复 name-registered native 注册映射/实现入口，验证一条真实脚本→native→返回调用；同时需实现属性、序列化及引擎服务。当前没有运行兼容 VM、加载地图、渲染首帧或中文显示。
