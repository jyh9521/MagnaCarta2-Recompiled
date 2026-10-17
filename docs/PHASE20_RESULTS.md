# 阶段20：完整byte flag恢复与新资源阻塞

## Verified
独立验证原82E078C0完整12bytes、原版本/邻居/44484PDATA、读取语义与r3/r11完整64-bit副作用。256byte×12地址3072例原样生成体完整正常返回；fullcontext除r3/r11不变，八页和MXCSR不变，compile/run0。不是标题实际bit值/fault/MMIO/全部硬件证明。
[独立语义](RESEARCH_BYTE_FLAG_LEAF.md)、[复现与AV观察](EXPERIMENT_BYTE_FLAG_LEAF.md)。

## 严格生成、全量编译链接
仅新增原12byte入口hint，完整继承旧11项hint/原字节守卫。新树9f5eda2bd7aa3934a32187063b2365864f502927ed67984f3cc02fa740d8fee6，58170共同body不变、只新增1函数，无删除。58171函数/58417映射，静态审计zero finding，197/197新TU以/fp:strict全量编译，显式NOREF/NOICF无FORCE宿主链接通过；没有修改SDK、原表或生成C++。
原SDK1193文件、15组2955历史/新对象和原生成输入重新hash通过。22成员根与原游戏资源不改。

## 真实入口与下一阻塞
同一22根：旧模块基线82E078C0未登记/C0000409；新模块推进原82390A70写guest3/C0000005。首轮未强制panic捕获，随后同一EXE只开启已有只读panic flag重跑，实际message/保存的原变参指向 `..\MC2Game\CookedXenon\PreF_VJuto_Base2.xxx`；savedLR824844F4，故障后headerword0、16bytes全零。
新实际PE fault RVA06FA8C14/894803（mov [rax+3],ecx）与原91000003/完整panic/caller独立核验，不把nearest symbol当源码证明。捕获message168bytes、filename88bytes均含UTF16BE终止符。
该原ISO成员offset3419625472、size1572864、SHA d5b57c3af82e17d6ad69478790d09a9b74d3cd55bba2a87639114c05285a22ca，严格BE446/25/header177867/4chunk summary通过；22根磁盘/staging/运行前后记录均缺该包，SDK两次找不到。只重读成员且复用阶段19整ISO身份，不声称本阶段重hash整ISO。
下一项在新独立根做该单成员部署A/B及实际行为回退，不直接改当前22根。与WoodSword已证受控因果不同，本次新文件的缺部署尚未通过干预建立零头唯一因果；postfault不是比较瞬间原子快照。未部署它或跳过原panic。

## 早期AV、失败与回退
精确只读observer与严格parser接线完成，独立SDK/XEX字节审查无阻断；12tests/14mode合成私有页fixture通过，但不冒充真实AV复现。两次修改后真实入口均not_observed；原坏CS指针的上游对象/初始化/并发写历史仍未证，未修复。
所有metadata RED、生成体模板首次拒绝、坏XEX拒绝、profile RED/GREEN及原native失败保留；一次私有patch脚本因预期两守卫相邻（实际中间有FP校验）断言失败，未写源码，分行精确修改后guard测试通过。
根770测试(skip2)、catalog及源码隔离732→770→732回退验证；恢复215原文件hash并移除8新增，主223源码保持修改态。真实行为回退使用恢复源码/旧197模块/同22根，重现82E078C0原fatal，不删新模块或原资源。
精确BASELINE/MODIFIED/ROLLBACK命令/输入/字面输出/exit、四件套在ignored local/analysis/phase20/verification/。远端、新clone及四项CI交付另核验。尚无首帧、操作、音频、战斗、存档、换盘或可玩性验收。
