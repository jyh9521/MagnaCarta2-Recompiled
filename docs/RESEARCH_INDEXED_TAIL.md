# 有界索引与间接尾调用入口

## 原72bytes与双路径（Verified）

独立工具 `verify_indexed_tail.py` 使用固定Disc1 XEX、loader及内存image hash守卫。`82A3DEA0..82A3DEE8` 的72bytes SHA256=`da78cc530445e6be3717bc6cec9e6cf949e163d65dc481ee5d6f63d4648b708a`：

```text
8943003c548b063e7ca92b787cc533787f0b5040419800103c608007606300574e80002081430024556b18387ce63b787d244b787c6b502e81630000814b00107d4903a64e800420
```

前一word=`4E800420 bctr`，后一word=`8943003C lbz r10,0x3c(r3)`；目标无包含PDATA。完整范围包含invalid-path的BLR和valid-path末尾BCTR，不按第一个返回截断，不标记为PDATA范围。

|阶段|精确状态与顺序|
|---|---|
|共同前置|读U8 count=[原object+3C]→r10；r11=r4低8bit；r9=原r5完整64bit；r5=原r6完整64bit|
|比较|unsigned cmplw CR6，selector<count时LT，等于时EQ，否则GT；SO复制XER.SO|
|invalid（selector>=count）|lis+ori令r3完整raw64=`FFFFFFFF80070057`，不是零扩展的`0000000080070057`；完整返回，CTR/LR不改；r4/r6仍保持原值|
|valid|r10=BE32[原object+24] table；r11=selector*8；r6=原r7，r4=r9=原r5，r5已是原r6|
|索引/调用|r3=BE32[table+selector*8] selected；r11=BE32[selected] vtable；r10=BE32[vtable+10] target；CTR=r10零扩展，BCTR非link尾调用，LR不改|

两路径均无store；其它GPR/CR、XER、所有FPR/vector/FPSCR不变。`r9/r5` 在范围检查前已被改写，因此invalid路径不能只核对返回值。rawr4的高位及低32bit的bits8..31均不参与selector。count、table、object和vtable是夹具字段标签，不代表已恢复业务类名、集合意义或真实对象生命周期。

oracle只接受原18-word模板、32项unsigned64 GPR、合法CR/SO/CTR和显式有界byte字典；按真实顺序读取，越界或缺字节即拒绝。有效地址按guest低32bit计算，BE32读取，不猜测缺失数据；invalid模型只读count，不投机读取table。无效/非对齐真实对象、MMIO、硬件异常/推测执行和完整Xenon验收不在此模型证明中。

## 范围合并不是代码消失

本轮新完整生成入口 `sub_82A3DEA0` 包含唯一 `loc_82A3DEC4:`，原valid block `82A3DEC4..82A3DEE8` 的36bytes仍在该body中。先前生成分析曾把这段单列为 `sub_82A3DEC4`；完整72byte范围使该宿主函数名/独立mapping被内部label取代。旧C++名称消失不等于原代码被删除，本差分也不足以证明DEC4不存在引用；原引用、PDATA及profile约束由独立范围合并审查处理。本工具不改生成树/hint或SDK。

## 标准库穷举与实际SDK差分

Verified：标准库真实穷举256count×256selector共65536例，32640 valid /32896 invalid，逐例核对索引目标、参数重排、invalid完整64bit返回和CTR等状态；不是抽样替代穷举。

实际generated harness另用1008代表夹具：7count边界值 ×9selector边界值 ×2SO ×4rawr4高位模式 ×2guest布局，初始CR6覆盖全部16值。576例执行完整invalid返回；432例执行到具名合成mapped-dispatch观察边界。

- **原生成body、`REX_CALL_INDIRECT_FUNC`、所有内存/FP宏都未替换**。在隔离harness的真实per-module dispatch表里，将4个明确标记的合成target slot映射到记录观察器。
- 真实宏执行原bounds check与nonnull slot lookup，然后调用观察器。此实验覆盖mapped lookup，不覆盖global resolver fallback；合成slot不是标题正式注册/原callee执行证据。
- 观察器在入口记录完整PPCContext与全部9页memory比较结果，验证传入r3/r4/r5/r6、CTR/LR、其它寄存器和读取后无store；不返回伪造游戏结果。
- 无需改dispatch宏或猜SDK私有偏移；实际链接官方 `rexruntime.lib`，实际加载DLL通过GetModuleFileNameW路径与整个文件SHA固定为 `e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a`。DLL被加载不等于初始化了游戏Runtime或执行原callee。
- 完整PPCContext按字节比较，包括全部FPR/vector、CR、XER、SP、LR、CTR及诊断字段；此mapped路径没有走fallback，因此也不应发明`last_indirect_target`变化。
- 4GB仅虚拟保留；8个合成guest页+1个dispatch页实际commit共36KiB，所有9页在边界/返回后均应不变。高地址guest使用真实Windows映射macro；地址`2000/4000/6000/8000`及`FFFEE000/FFFEC000/FFFEA000/FFFE8000`不是标题资源。

编译固定Clang hash并用 `/Od /fp:strict /MD /EHa /arch:AVX2`。hostMXCSR通过官方InitHost与cache一致，执行后单独核对并恢复。报告保留生成/SDK/Clang头、compiler/vcvars、runtime/importlib/Tracy文件前后hash；并不把这些明确哈希输入外推为整个系统headers或机器状态全未变化。

## 实测、失败与复现

首个原输入CLI `exit0`，原证明 `local/analysis/phase16/indexed-tail-original.json`，完整65536矩阵通过。自制badXEX实际CLI `exit1`，逐字 `ValueError: unsupported XEX hash`，输出不存在；保留 `indexed-tail-guard-failure.json` 和自制样本。

首个真实差分 `indexed-tail-generated.json` 为 **compile1、尚未运行**：clang-cl把`/link`前的绝对`.lib`当作额外源，逐字报 `cannot specify '/Fo...' when compiling multiple source files`。该失败的完整命令、compile日志、生成body与输入hash留在原目录，未覆盖或删除。随后仅调整harness驱动命令，将importlib交给`/link`，不改body、SDK或oracle。

最终 `indexed-tail-generated-final.json` 和 `indexed-tail-generated-final-harness/verification.json`：真实 **compile0/run0，1008全部通过**，DLL路径/hash验证=true、macro_replacements=false、所有明确输入前后unchanged=true。原body SHA256=`7d12e2ed39cec1c21ea4d851d30a81732342c292f37d545247747721ac459ecf`。逐例run日志包含rawr4、完整rawr3和CTR、调用次数及context/memory/ABI/host结果，末行：

```text
INDEXED_MEMORY pages=9 invalid=576 tail_boundary=432 released=1 failures=0
```

```powershell
python -m unittest discover -s tests -p test_indexed_tail.py -v
python -m tools.research.verify_indexed_tail --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --output local/analysis/indexed-tail-reproduction/original.json
python -m tools.research.verify_indexed_tail --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --generated local/analysis/phase16/strict-codegen/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --output local/analysis/indexed-tail-reproduction/generated.json
```

输出要求新文件；harness使用旁边 `<output-stem>-harness` 新目录并拒绝进入输入树。四项工具链参数一起给出，SDK/compiler/module布局不匹配即拒绝。纯模型及tests仅标准库；原XEX路径复用已有cryptography解码，不依赖私有旧原像，不写密钥或原游戏数据。

14项标准库tests包含65536穷举、raw64错误值、early参数变化、低8bit截取、stride8读取地址、缺memory/类型/边界拒绝、唯一body/mapping/布局守卫、未替换macro及完整边界context/memory合同。标题运行、真正callee语义和后续动态阻塞仍以独立实际标题实验为准，不把合成dispatch观察器当作运行时修复或可玩验收。
