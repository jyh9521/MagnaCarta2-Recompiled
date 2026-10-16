# 双返回 bitfield 叶入口独立验证

## 原字节与范围（Verified）

Disc1原 XEX/loader/image 的既有hash守卫通过后，`82AC2810..82AC2830` 的32bytes为 `81630020556abffe556bc7fe2b0a0000616300024c9a0020556307fa4e800020`，SHA256 `9174c77a101ea25e91a9fb0f1b8c9c7e512c4b7fdc7d80af0ce39fbfbe311f6a`。

没有包含此入口的原 PDATA；前一word=`4E800420 bctr`，下一word=`9083003C stw r4,0x3c(r3)`，配合本叶的两个返回构成保守32-byte边界，不称为PDATA证明或完整类/vtable恢复。原路径恢复由独立有守卫hint实验负责；本工具不改hint、生成树、SDK或原文件。

|地址|原指令|整数模型|
|---|---|---|
|82AC2810|lwz r11,0x20(r3)|读BE32，r11零扩展至64bit|
|82AC2814|rlwinm r10,r11,23,31,31|r10=(word>>9)&1，零扩展|
|82AC2818|rlwinm r11,r11,24,31,31|r11=(word>>8)&1，零扩展|
|82AC281C|cmplwi cr6,r10,0|CR6 lt=0，gt=(r10!=0)，eq=(r10==0)，so=XER.SO|
|82AC2820|ori r3,r11,2|r3=r11\|2|
|82AC2824|bnelr cr6|BO4/BI26，CR6.eq为假时早返；不是beqlr|
|82AC2828|rlwinm r3,r11,0,31,29|PPC64环绕mask=FFFFFFFFFFFFFFFD，清bit1但不清全部高32位|
|82AC282C|blr|普通返回|

因此**低32bit**返回 `(word>>8)&3`；原始64bit r3在bit9=1时为2或3，bit9=0时为 `bit8 * 0x0000000100000001`。输入bit9为1时走bnelr，否则走末尾blr。**只比较返回值不够**：r10/r11和CR6都被覆盖，r10/r11高32位清零，但末条wrap-mask可生成r3的bit32，不能把所有rlwinm误当零扩展。XER仅提供SO且自身不改变；其它GPR/CR、LR/CTR、全部FPR、FPSCR、vector和内存不应变化。本模型只处理明确有效、对齐的普通内存读取，不声称MMIO、缺页、异常或硬件执行证明。

## 独立模型与真实生成差分

`rotate_mask()` 按PPC64定义复制低32bit为64bit并旋转，再用64bit `MASK(MB+32,ME+32)`（包含跨bit63→0环绕）实现，不把整叶替成返回值公式；`execute()` 先逐步骤维护r11/r10/CR6/r3，再选择双返回路径。仅接受原八word模板、32项unsigned64 GPR、合法CR6/SO/BE32输入；未知模板/类型/越界立即拒绝。

真实harness从 fresh生成树提取唯一完整body，并检查init mapping与registrar恰好一次；拒绝REX_FATAL、callee、store或缺少双return的形状。body原样编译，真实SDK context与内存macro均不替换。

2048夹具覆盖4种关键bit组合 ×8种其它bit背景 ×2种XER.SO ×16种初始CR6 ×2种guest地址；原GPR都有非零高位并覆盖不同高位模式，分别验证早返与末尾返回。每例完整PPCContext字节比较预期仅r3/r10/r11/CR6变化，因此所有FPR、FPSCR、LR/CTR/其它CR/GPR/vector同时受检。两页稀疏guest地址 `2000/FFFEE000` 通过真实macro映射，初始化后整页快照；所有8192bytes都必须保持不变。hostMXCSR经官方InitHost使cache一致，执行后单独检查未变并恢复。

编译使用与当前strict浮点合同一致的 `/Od /fp:strict /MD /EHa /arch:AVX2`，不通过关掉断言、重写条件或stub取得成功。源树、SDK头、编译器头和工具链前后hash检查与完整命令/输出留在忽略目录；标题运行、完整模块编译和真实下一阻塞分别由主阶段报告。

## 复现

```powershell
python -m unittest discover -s tests -p test_bitfield_leaf.py -v
python -m tools.research.verify_bitfield_leaf --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --output local/analysis/bitfield-reproduction/original.json
python -m tools.research.verify_bitfield_leaf --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --generated local/analysis/phase14/strict-codegen/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --output local/analysis/bitfield-reproduction/generated.json
```

输出必须是新文件；四项工具链参数必须一起给出，harness进入旁边 `<output-stem>-harness` 新目录，拒绝进入输入树。纯整数模型和tests仅用标准库；真实原XEX解码复用已有hashlocked loader入口及cryptography，不依赖旧私有原像，不保存密钥。

首个真实original验证CLI exit0，证据 `local/analysis/phase14/bitfield-original.json`。真实badXEX入口exit1、原文 `ValueError: unsupported XEX hash`、输出不存在；完整命令/输入hash/stderr在 `bitfield-guard-failure.json`，自制坏样本与失败原样保留。标准库tests覆盖全部相关bit、1万随机word、环绕mask、SO/初始CR/GPR高位、未知模板/类型/范围、body/mapping/工具链守卫和harness完整状态检查。


## 已验证：原假设失败、按独立定义纠正后通过

首次 `bitfield-generated.json` 真实 compile0/run1，2048例中512例完整context不符，memory/host均通过。原因是**研究oracle错误**：最初把最后一条rlwinm的环绕mask限定32bit，误期望bit8=1且bit9=0返回1；真实生成体返回 `0000000100000001`。该失败目录 `bitfield-generated-harness`、旧oracle fixtures/CPP/obj/run及初版 `bitfield-original.json` 完整保留；后者的字节守卫有效，但旧oracle结果已被本节纠正，不能当最终64bit语义。

修正不是为了拟合生成结果：独立审读[固定Xenia95a5c3ee `ppc_emit_alu.cc`](https://raw.githubusercontent.com/xenia-project/xenia/95a5c3ee250f80c3b9d139658649d9ffb6db3eec/src/xenia/cpu/ppc/ppc_emit_alu.cc) 1027..1055（本地SHA256 `21fc8209238e4456739cc6df4d20782c8b8d3e24ec1c4f3c78f5f831972c529b`）明确先duplicate再 `XEMASK(MB+32,ME+32)`；[官方PowerISA v3.1C文档](https://files.openpower.foundation/s/9izgC5Rogi5Ywmm/download/OPF_PowerISA_v3.1C.pdf)（本地SHA256 `56372d23ece7e9e2c1b381a639443982a3e16e38109df1c141d655b779b61fdb`；实际footer v3.1C-rc3/99a1cac/2023-06-22）PDFpage42/printed6定义 ROTL32 为64bit `x||x` 的旋转、MASK跨边界时环绕，PDFpage144/printed108给出rlwinm对应公式。MB31/ME29实际为MASK63,61，因此高32bit并非总清零。这是独立参考实现与架构定义支持的修正，不是SDK补丁或物理Xenon实测。

纠正后新目录 `local/analysis/phase14/bitfield-generated-final.json`、`bitfield-generated-final-harness/verification.json`：实际 `/Od /fp:strict` **compile0/run0，2048全部通过**。原生成body SHA256始终 `712829a73efd11c6048a2c91f452548b57fec7b520040163829b258a3df5f00c`；生成/SDK/编译头/工具链前后unchanged=true。完整逐例输出保留r3/r10/r11 raw64、CR6、memory/context/host结果。末行原文：

```text
BITFIELD_MEMORY pages=2 early=1024 late=1024 released=1 failures=0
```

early/late是根据已验证原分支条件分类的输入计数，不是额外CPU分支跟踪；真实原样body的两个return及两类输入的完整状态结果一起受检。原样body没有REX_FATAL/补stub或callee/store。SDK与生成源码从未为修正oracle而修改。

最终标准库测试12项 `OK / exit0`（`bitfield-tests-final.txt`），新增PPC64 wrap-mask回归和原bnelr BO/BI/XO/LK字段核对；真实badXEX拒绝及首轮512模型失败都未删除。
