# 阶段16：完整索引尾分派与真实入口推进

## Verified：原范围与语义
82A3DEA0..82A3DEE8完整72bytes，SHA da78cc530445e6be3717bc6cec9e6cf949e163d65dc481ee5d6f63d4648b708a，无PDATA。原XEX、展开像、loader及相邻边界独立核验。
原count为object+3C的byte，selector为r4低byte，CR6 unsigned比较继承XER.SO。比较前原r5已复制到r9、原r6已复制到r5，即使非法路径也必须保留这些变化。
非法selector>=count返回full64 FFFFFFFF80070057，不读表；合法路径读object+24表、selector*8的对象及其vtable+10，按原r5/r6/r7重排r4/r5/r6后经CTR尾调用。LR/SP保持，不写内存。selector255始终非法。

## Verified：独立oracle与真实生成body
14项新回归包含全部65536 count/selector组合：32640合法、32896非法。
原样生成body/真实SDK宏及真实rexruntime DLL，1008实际差分全部通过：576非法完整返回，432合法仅合成dispatch的tail ABI边界，不执行真实callee。
完整PPCContext、九页内存、LR/SP/CTR及实际DLL路径/hash均核验；不将合成dispatch当标题原vtable。
首次harness编译exit1保留，原因是.lib放在/link之前触发clang-cl多输入/Fo冲突；仅修正链接参数位置后compile0/run0。
研究与复现见[原语义](RESEARCH_INDEXED_TAIL.md)、[实验](EXPERIMENT_INDEXED_TAIL.md)。

## Verified：函数合并而非简单新增
严格生成首次身份断言失败已保留：旧sub_82A3DEC4实际是合法分支后半段，现在并入新parent的loc_82A3DEC4。
58168共同body不变，旧DEC4 tail正文与新parent内部正文逐字相同；函数总数仍58169、映射仍58415，不是各加一。
独立扫描原非discardable sections：DEC4唯一直接分支来自内部82A3DEB4；无对齐非代码指针、代码字面值或有界16指令地址对引用，无PDATA/旧生成直接caller。该结论不排除未知计算或未对齐引用。
未添加alias、未修改SDK/生成C++/原表。397源新树d8336966f006a40c572f70585fbf4c3880554eca6669385d24605fde5a86ffd4。
197TU/58169函数审计零finding，197/197全量/fp:strict编译、NOREF/NOICF无FORCE链接；AMD64 PE、全部函数map、三个header快照独立验证。
SDK1193文件、13组2561对象、原生成树及两张完整ISO重新hash不变。原299 indexed-native最终效果匹配，不是逐ctor跟踪。

## Verified：真实标题与下一阻塞
同一21原成员根、真实presenter、无hook、45秒：旧phase15模块到82A3DEA0原fatal；新模块到82B7CCD0原fatal，均C0000409/3221226505，诊断CLI exit0。
当前LR82B00EB8/CTR82B7CCD0，原caller82B00EB4的slot4C已核验。新target原8bytes 806300344e800020，SHA bbf1454f181f2d9d96316fad7d3c753d45df4678c1bafd0fe0217f84fa9b906f，无PDATA，语义为BE32[object+34]零扩展返回。尚未执行该target，字段值未知，下一阶段先独立验证再恢复。
同次日志另报缺wp_Juto_st1_0_WoodSword.xxx；原Disc1确有该196608byte成员，member SHA f3ffd312d751b85a5d2cd954ff42a51bc1c012dfb5f272db09a5adb92177f85e，当前21根未部署。只读核验，未提取/部署/重跑；缺包和明确未登记fatal分开记账，未建立因果关系。
当前栈不能证明恢复函数当次具体分支或真实callee执行。GPU depth target不是swap/可见首帧，没有可玩性验收。

## 测试与交付
根目录662测试(skip2)；隔离baseline641/modified662/restored641(skip3)，原190文件hash恢复、新增6文件移除，主目录196文件保持修改态。
实际行为回退以旧phase15严格197对象、同一21根重现82A3DEA0原fatal；源码事务不修改原资源。精确命令、literal输出、exit与四件套保存在ignored local/analysis/phase16/verification/。
首次身份断言、harness编译、badXEX拒绝及先前失败全部保留。提交前后另核验远端、全新clone和四项CI；原资源/生成代码/二进制不入库。
