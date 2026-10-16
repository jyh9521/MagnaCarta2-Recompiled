# 阶段13：原浮点叶、严格FP合同与下一原入口

## Verified：版本、原体与实际生成差分

原XEX/loader及完整展开映像hash守卫通过。82AC1DE8原20-byte/5指令、无包含PDATA、前BCTR/后padding独立核验。
原序列依次lfs object+0x30→stfs r4、lfs object+0x34→stfs r5→blr；先store可覆盖第二source，不能同时预读或直接memcpy两float。
整数IEEE32/64 oracle明确RNE/gradual与quiet/preserve NaN策略，不假装硬件FPSCR完整模型。

实际原样生成body使用SDK内存/FP宏、768夹具/配置，覆盖12输入类×4别名×4round×4flush，完整context和两页内存比较：
- Od：compile0/run0，768通过。
- rawO2：compile0/run1，160项memory差异；原失败/机器码保留。
- O2 + /fp:strict：compile0/run0，768通过。

机器码确认rawO2消去double→float回转，sNaN输出仍signaling而FPR0已经quiet；strict保留两对转换。
因此通用compile_module显式固定/fp:strict并记元数据；新float-leaf标题profile还检查所有对象argv，非strict构建会拒绝。
旧profiles保留真实行为回退兼容。只修构建合同，不改SDK、原指令、vtable、GNatives或生成C++。
详情见[原叶研究](RESEARCH_FLOAT_LEAF.md)，复现见[实验](EXPERIMENT_FLOAT_LEAF.md)。

## Verified：严格生成、全量编译/链接与真实标题

strict生成397源文件；58166共同函数正文逐字节不变，仅新增sub_82AC1DE8。partition重分配引起多数源归属变化，不是函数正文重写。
新树cddd7af7516965eb293c850fb07b20e5b6976f759addf906b52ea441e8869767；197源/58167函数审计0 findings，58413映射。
原defaultOd与最终/fp:strict各197/197新目录全量编译通过；最终197对象以NOREF/NOICF显式链接AMD64宿主，独立map逐函数复核。
SDK1193文件、十组1970对象、全部生成树和两张完整ISO身份保持不变；新对象与旧构建并存，原21成员根不增加资源。

同一21原成员根/真实GPU+presenter/无hook45秒：
- BASELINE旧phase12模块：实际82AC1DE8原fatal，exit3221226505。
- 初次新入口defaultOd和最终strict：均实际82AC2810原fatal，exit3221226505 (C0000409)。
- LR82AB2CEC/CTR82AC2810，原caller82AB2CE8 bctrl；host栈sub_82AB2AF8。

旧fatal消失与新位置是实际进展；未逐指令跟踪标题中的82AC1DE8调用，不把更远位置当每条路径执行证明。
新的82AC2810尚未登记/执行，未添加第二hint，未跳过原fatal。原299项indexed-native最终效果仍匹配，不是逐ctor追踪。

## 下一阻塞：Verified边界与High-confidence静态语义

82AC2810..82AC2830原32-byte/8指令，SHA9174c77a101ea25e91a9fb0f1b8c9c7e512c4b7fdc7d80af0ce39fbfbe311f6a，
无PDATA，前BCTR/后独立stw叶；两个return必须包含在同一范围。
原caller经vtable+0x68分派。静态推导返回(word[r3+0x20]>>8)&3，同时改变r10/r11/CR6；不只是纯返回表达式。
实际输入word/返回值、对象属性名未知。下一项先独立所有bit组合与寄存器/CR副作用差分，再恢复完整范围，不将内部return切断。
这轮是明确未登记fatal，不是缺包AV或等待超时；可选路径失败仍完整保留而不强行解释为因果。

## 测试、失败与回退

根目录带SDK604测试(skip2)与catalog通过；隔离源码/clean clone缺本地SDK时skip3，真实SDK差分另已执行。
基线575→修改604→恢复575，隔离回退原172文件hash恢复、6新增文件移除，主目录保持修改态。
实际回退使用恢复源码+旧phase12构建和同一21根45秒present，无hook，重现82AC1DE8 C0000409，不改回资源/SDK。
完整命令、输入、literal输出和退出码在local/analysis/phase13/verification/，含MODIFIED_FILE.py、DIFF_FILE.patch、VERIFICATION.txt、可执行ROLLBACK.sh。
推送/远端HEAD/全新clone/CI在交付记录分别核验。原资源、生成代码、二进制与完整日志均只在ignored local。

保留rawO2的160差异、弱alias section0无效解码、错误测试导入路径、Git blob混合换行快照纠正、cp932文档读取失败、REA不支持XEX。
没有可见首帧、正常标题关闭、地图/战斗/输入/音频/存档/换盘或可玩性验收；FP硬件异常/NaN全模式等价仍未知。
