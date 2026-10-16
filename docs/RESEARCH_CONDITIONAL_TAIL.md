# 条件返回与直接尾调用原入口

## 原版范围（Verified）

`tools/research/verify_conditional_tail.py` 只读固定Disc1 XEX，复用既有XEX/loader hashlocked内存解码并验证imageSHA。原 `826A9EC8..826A9EE8` 恰32bytes：`814301087c6b1b7880630080554900c22b030000912b01084d9a00204801fa3c`；SHA256 `8b4df364b42994f970049966b3a8c5db4528bc3c6a18c3f7cd2a78b35d0501a7`。前一word=`4E800420 bctr`，后一word=`4E800020 blr`；目标无包含PDATA。本范围终止于直接非link branch，不在条件返回处截断，不把该保守范围称为PDATA边界。

|地址|原指令|顺序与完整状态|
|---|---|---|
|826A9EC8|lwz r10,0x108(r3)|从原object读BE32 flags，r10零扩展|
|826A9ECC|mr r11,r3|保留原object的**完整64bit**值|
|826A9ED0|lwz r3,0x80(r3)|从原object读member，r3零扩展|
|826A9ED4|rlwinm r9,r10,0,3,1|PPC64重复低32bit并用MASK35,33环绕；mask=`FFFFFFFFDFFFFFFF`|
|826A9ED8|cmplwi cr6,r3,0|unsigned比较；lt=0，gt=member非0，eq=member为0，so=XER.SO|
|826A9EDC|stw r9,0x108(r11)|将r9低32bit写回**原object**flags；两分支都先写|
|826A9EE0|beqlr cr6|BO12/BI26/LK0，member为0时返回|
|826A9EE4|b 0x826C9920|AA0/LK0直接尾调用；该原范围不改LR/CTR|

flags清低32bit的bit29；**完整r9**为 `(uint64(flags)<<32) | (flags & DFFFFFFF)`，不能把阶段14已纠正的wrap-mask再退化成32bit零扩展。其余GPR、CR字段、XER、全部FPR/FPSCR/vector不变。尾目标接收r3=member，r4/SP等其它参数保持原值；没有证据给该branch发明CTR写入或link LR。

PPC64旋转/mask依据见[双返回入口研究](RESEARCH_BITFIELD_LEAF.md)内固定官方PowerISA定义及Xenia95a5c3ee源证据；本工具独立用64bit位号集合构造MASK35,33。静态模型不是物理Xenon、异常/无效地址/MMIO或完整对象类型证明。

## 生成差分的精确边界

原32bytes模型逐步维护r10/r11/r3/r9/CR6和唯一store，不以一个返回值公式替代状态。原XEX/loader/image/range、前后word、无PDATA和末条直接branch目标均先守卫；未知opcode/template/类型/字段立即拒绝。

真实生成harness检查唯一完整入口body、entry与现有tail的init mapping/registrar恰好各一次；body不得含REX_FATAL/间接调用，须保留两load/一store、条件return及唯一直接tail。原生成入口body、SDK context、FP和内存macro保持原样。

- **null路径**：完整执行该原样生成body，真实条件return，外部观察器调用次数必须0。
- **nonnull路径**：执行到外部直接尾调用边界。仅本地隔离harness用具名 **external-tail ABI observer** 记录该边界，不执行、模拟或宣称原 `826C9920` 的结果。观察器在入口即复制完整PPCContext，并读取已写flags；立即与预定oracle比较，所以store-before-tail和完整参数状态受检，而不只是检查函数最终返回。
- 标题运行/正式生成树没有安装该边界观察器；运行时缺函数不由它隐藏。JSON始终明确 `tail_callee_execution=NOT-TESTED`；即使tail原先已有mapping，也不是callee已执行证据。

原callee `826C9920..826CA5EC` 有PDATA、3276bytes；开头有保存寄存器helper、384byte stack frame、另一原函数调用和依赖r4的浮点/成员操作。本轮没有用猜测对象结构构造“成功callee”，而将验证停在有明确ABI的尾边界；真实调用链和下一阻塞以独立标题运行报告为准。

## 矩阵与复现

2560夹具：8种flags背景 ×5种member（含0及非零极值）×2种XER.SO ×16种初始CR6 ×2种guest地址。512例为null完整返回，2048例为nonnull尾边界；非零member在隔离边界实验不被解引用，不据此认定它是有效真实对象。

全部GPR初始化非零高位；完整PPCContext按字节比较预期仅r3/r9/r10/r11/CR6变化，明确包含LR/CTR/SP/r4、全部FPR/vector/FPSCR。真实SDK宏在 `2000/FFFEE000` 两稀疏guest页映射上执行，完整8192bytes只允许原object+108四字节变更。hostMXCSR通过官方InitHost形成一致cache，执行后单独验证不变并恢复。编译固定Clang hash与 `/Od /fp:strict /MD /EHa /arch:AVX2`；源码/SDK头/编译头/工具链前后hash保留。

```powershell
python -m unittest discover -s tests -p test_conditional_tail.py -v
python -m tools.research.verify_conditional_tail --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --output local/analysis/conditional-tail-reproduction/original.json
python -m tools.research.verify_conditional_tail --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --generated local/analysis/phase15/strict-codegen/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --output local/analysis/conditional-tail-reproduction/generated.json
```

四项工具链参数须一起给出；输出要求新文件，harness使用旁边 `<output-stem>-harness` 新目录且拒绝进入输入树。纯模型/tests标准库可跑；实际XEX路径需要既有cryptography依赖，不依赖旧私有原像、不输出密钥、不修改原文件。

首轮实际原验证CLI exit0，证据 `local/analysis/phase15/conditional-tail-original.json`；实际unsupported XEX CLI exit1、逐字 `ValueError: unsupported XEX hash`、无输出文件，保留 `conditional-tail-guard-failure.json`。tests覆盖1万随机flags、64bit wrap-mask、null/nonnull和ABI保留、BO/BI/XO/LK/branch字段、唯一store及先后顺序、非法字段/模板、完整context/内存与边界观察器合同、mapping/body/半套工具链拒绝。失败记录不删除，不将尾边界记录当作完整callee执行或标题成功。


## 已验证：真实原样生成体差分

最终 `local/analysis/phase15/conditional-tail-generated.json` 与 `conditional-tail-generated-harness/verification.json` 为实际 compile0/run0，**2560例全部通过**：512例完整null返回，2048例只到具名外部tail ABI边界。body SHA256 `a7570ea57cd99680bbee653579671bbd3a573fd518a1fc78b7cce4af9af664bf`；原样body确实先执行真实store，再 `if(ctx.cr6.eq)return;`，否则直接 `sub_826C9920(ctx,base);return;`。入口和tail在init+registrar各唯一登记，无REX_FATAL。完整生成/SDK头/编译头/工具链前后unchanged=true，原XEX/loader前后hash也一致。

`compile.txt`为空诊断，`run.txt`保留所有逐例完整raw64寄存器、CR6、tail次数、写后位字与memory/context/ABI/host比较；末行逐字为：

```text
CONDITIONAL_MEMORY pages=2 null=512 tail_boundary=2048 released=1 failures=0
```

11项标准库测试 `OK / exit0` 留存 `conditional-tail-tests-final.txt`。首轮自制badXEX拒绝仍保留；未修改SDK、生成body或原像来取得差分通过。独立callee可行性原字节/PDATA证据另存 `conditional-tail-callee-boundary.json`；它不是执行结果。`flags/member` 是夹具字段标签，不宣称已恢复类、枚举或业务意义。
