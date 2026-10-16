# 原始 BE32 word-load 叶入口

## 原范围与语义（Verified / 静态）

本阶段在当前 `MagnaCarta2-Recompiled` 实体仓库执行。工具先对用户提供的Disc1 XEX、固定loader源和解码image作SHA守卫；不使用旧私有image.bin，不写原像或密钥。

`82B7CCD0..82B7CCD8` 恰8bytes：`806300344E800020`，SHA256 `bbf1454f181f2d9d96316fad7d3c753d45df4678c1bafd0fe0217f84fa9b906f`，即：

1. `lwz r3,0x34(r3)`：读取原r3低32bit加34后的BE32，零扩展至完整64bit r3。
2. `blr`：正常返回，LR/CTR寄存器值不写回改变。

原image SHA256 `d18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9`。没有包含该入口的PDATA；前16bytes=`806300384800D2B4806300384800D40C`，前一兄弟尾部为直接branch；后16bytes=`548B033E396B001B556A083C7D6B5214`，从82B7CCD8开始另一段操作。全部邻居字节及各自hash保存于original报告并守卫。8byte是该已知入口的保守完整叶范围，不冒称PDATA或完整类边界。

本项目32bit guest地址合同的有效地址为：

```text
EA = (rawR3.low32 + 0x34) mod 2^32
newR3 = zero_extend_64(BE32(memory[EA:EA+4]))
```

其它GPR、所有CR/XER、FPR/vector、FPSCR、LR/CTR及内存不变。字段的业务类型/真实标题返回值没有从这个load推定；纯模型与生成函数夹具不是物理Xenon或完整标题执行证明。

## 独立整数/byte oracle

`execute()` 只接受原两word模板、32项unsigned64 GPR和显式byte字典；由四个独立BE bytes解码，不使用host float、union或原SDK load/store作为oracle。输入寄存器/字典不修改；仅复制后的r3改变。缺字节、未知模板、bool伪装整数、越界字段及未对齐访问明确拒绝。本研究只验证普通、有效、对齐且已映射的word；fault、MMIO、未对齐、权限/异常和硬件控制流不由模型声明已通过。

1536例 =128种payload ×12种EA布局。payload有0/1、7FFFFFFF/80000000/FFFFFFFF、字节序哨兵及固定seed1701的116个随机word；所有GPR与upper-r3使用确定性随机值，另含upper=0和FFFFFFFF边界。

EA覆盖低页、页尾/下一页、`FFFEE034`、`FFFFEFFC`、`FFFFFFFC`、wrap后`0/4/30`、物理映射阈值`DFFFFFFC/E0000000/E0000FFC`。不能先对raw64r3做完整64bit加法后才使用结果，也不能让r3旧高32位残留在返回值中。

## 原样生成体实际差分

提取fresh生成树中唯一完整 `sub_82B7CCD0`，守卫唯一init/registrar登记、精确load/return形状和预期原macro合同；**将提取到的完整body原样编译，不用手写body代替，也不改SDK、macro、表或stub**。实际body SHA256 `353e84404ed1eadb80ad348ed7768142f2116dbd91d91f36064d0e35dfd96a0d`。

独立BE逐字节初始化payload，而不是先用SDK STORE再用SDK LOAD使双重错误抵消。物理位置按独立Windows公式计算，并断言真实 `REX_PHYS_HOST_OFFSET` 与该公式一致：先把EA截为32bit，再对EA>=E0000000加0x1000的host bias。

因此guest `FFFFFFFC` 的host读取位于base+`0x100000FFC`；只reserve4GiB会越界。本夹具reserve `0x100001000` bytes（4GiB+一页），只commit8个必要host页共32KiB。guest零页是隔离夹具故意映射的内存，不表示标题真实null页可读。

每例对全部8页作完整byte快照及比较；完整SDK PPCContext按字节比较，预期只允许r3改变，包括全部GPR/FPR/CR/XER/vector、LR/CTR、padding与FPSCR存储。FPR另置raw sNaN、qNaN、signedzero和infinity哨兵，不做浮点转换。官方InitHost使cachedCSR和实际MXCSR一致，覆盖不同round/flush/sticky种子，执行后分别核对MXCSR未变并恢复。这个cachedCSR检查不是完整guest FPSCR硬件仿真。

编译器hash、SDK context/FP header已固定；实际flags为 `/Od /fp:strict /MD /EHa /arch:AVX2`。生成/SDK/Clang头树及compiler/vcvars前后hash记录不等于整个系统headers或机器状态均受保护。

## 已完成实测与限制

首轮原验证CLI exit0，1536 oracle例通过；记录 `local/analysis/phase17/word-leaf-original.json`。实际新生成体差分保存在 `word-leaf-generated.json` 和 `word-leaf-generated-harness/verification.json`：**compile0/run0，1536例全部通过**，无编译诊断，macro_replacements=false，明确哈希输入前后unchanged=true。每例实际执行完整load/return，没有tail观察器或被替代callee。

主CLI逐字输出、退出码0：

```text
WORD_LEAF original=verified cases=1536 success=True title=NOT-TESTED
```

实际run末两行：

```text
WORD_CASE 1535 raw3=919BE166E0000FC8 ea=E0000FFC payload=D7E91B52 r3=00000000D7E91B52 memory=1 context=1 mxcsr=1 success=1
WORD_MEMORY pages=8 cases=1536 released=1 failures=0
```

`completed_without_fault` 初始false；只有实际进程exit0、全部逐例记录唯一且按顺序完整、最终释放记录正确且无stderr后才可设true。partial stream、异常exit、缺最终记录、重复/畸形case均不能提前宣告完成。本次该字段true仅指以上有效映射夹具正常完成，不外推fault/MMIO/未对齐、真实标题数据和游戏验收。

14项标准库tests `OK / exit0`；自制badXEX真正CLI exit1、逐字 `ValueError: unsupported XEX hash`、输出不存在，完整命令/输入hash/stderr保留 `word-leaf-guard-failure.json`。本阶段生成体首轮即通过，没有删去失败重跑；拒绝记录与所有测试日志均保留。

## 复现

从本项目工作根执行；输出须为新文件，四项工具链参数必须一起给出。harness自动进入旁边 `<output-stem>-harness` 新目录，拒绝进入输入树：

```powershell
python -m unittest discover -s tests -p test_word_leaf.py -v
python -m tools.research.verify_word_leaf --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --output local/analysis/word-leaf-reproduction/original.json
python -m tools.research.verify_word_leaf --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --generated local/analysis/phase17/strict-codegen/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --output local/analysis/word-leaf-reproduction/generated.json
```

本轮实际最后一条的输出参数为 `local/analysis/phase17/word-leaf-generated.json`；其它参数相同。精确compiler argv、生成body/source/PCH hash、完整逐例输出、exe hash和exit status均在verification报告。纯模型/tests仅标准库；实际XEX解码另用既有cryptography依赖和有守卫loader源，不依赖私有中间映像。完整模块编译、标题实际下一阻塞和Git发布由独立主阶段报告。
