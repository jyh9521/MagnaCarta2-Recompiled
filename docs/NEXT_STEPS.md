# 第二十四阶段之后的实验门槛

## 已完成
三处条件分支、五组SEH边界均经PPC/PDATA证据修复；严格生成、独立静态审计、197TU全量Clang编译与两叶函数27输入差分通过。
七包12901个UFunction完成字段/native index/flags和token framing；缺口统计不等于native实现恢复。
197对象显式宿主链接、SDK tool_mode初始化、58408映射/内存往返释放/关闭通过；全模块真实Add native执行8组受控参数成功。
真实XEX装载后已移除vtable夹具；正式kernel/audio/input/GPU配置与小型原资源部署使标题进入main，8234FF10已由原版本入口hint严格重生并全量验证；823C2740已strict重生，比较回调C1A0完整恢复，C214保留内部label；52/61入口已严格恢复；同一20成员根接入真实presenter/隐藏窗口；等待元数据已观测为Event，旧61 fatal消失。

## P0：路线A宿主链接与运行时初始化
- 阶段24实际确认原callback持续执行：711inc/711reservation/709dec，余2为流动队列边界项；稀疏2>1不再解释为同一次wait卡45秒。下一项对原main每轮完成、8277B6D8→8244A360/8286E618的实际返回与提交/呈现建立时间轴。不要强减counter；旧AV未修复。见[阶段24](PHASE24_RESULTS.md)。
- 延时/正常CS观测已推进：原82869800完整0x90和调用条件验证；真实main parentLR82E2080C在采样时原counter83265218=2>1进行零延时轮询，非一次delay卡45秒。下一项追踪82399650原增计数/82399738潜在回调的实际dispatch与counter生命周期，不伪造完成或强减counter。正常CS/早期坏CS分开，CS keyoverflow不宣称全覆盖。见[阶段23](PHASE23_RESULTS.md)。
- voc原包单成员部署完成：同EXE23→24→23→24→23，三次23根voc原panic、两次24根45秒仍running/host exit26，两个实际回退恢复原panic。当前不是新fatal，而是调度/有限观察边界；精确采样涉及82869850→82E8DF4C/KeDelayExecutionThread。先独立验证原循环/延时条件，不把缺资源warnings、pipeline或无panic当首帧。见[阶段22](PHASE22_RESULTS.md)。
- PreF原包单成员部署已完成：同EXE22→23→22→23→22三次PreFpanic/两次voc_bt_juto_0.xxx原panic，资源实际回退均恢复PreF。23根保持部署态，下一项先独立原voc成员身份/加载条件，再新资源根单成员A/B及实际回退；本次已核验其原SHA/strict summary和23根缺失，不直接改23根或跳过原panic。见[阶段21](PHASE21_RESULTS.md)。
- 另保留早期AV：SDK RtlEnterCriticalSection_entry精确读CS+18，原入口对象字段+8再加4产生坏参数；原对象/写入历史未捕获。阶段21精确只读observer持续开启，五次真实运行not_observed；未宣称修复或资源唯一因果；若重现，限定记录原r29对象/r11/r30，不伪造CS。
- 82B7CCD0完整8-byte BE32读取/零扩展已strict恢复，1536实际body完整正常返回通过（8页/fullcontext/MXCSR，EA wrap与physical bias分开验证），58169共同body不改，197TU全量strict编译/58416映射链接完成；字段/标题实际返回值未知。
- 82A3DEA0完整72-byte已恢复，65536 oracle/1008实际body通过；432合法case仅tail ABI边界。旧DEC4并入parent，58169函数/58415映射保持不变，197TU严格重建实际推进82B7CCD0 fatal。另有原WoodSword包部署缺失，尚无其与fatal的因果证据。
- 826A9EC8原32-byte写入和条件尾调用已strict恢复，2560差分通过（512null完整返回，2048仅外部tail ABI）；197TU/58415映射实际推进82A3DEA0原fatal。当前真实栈不含826C9920，不能宣称其当次进入/完成；fixture也未执行原callee。
- 82AC2810完整32-byte双return已strict恢复，2048原body差分通过；原512 oracle失败保留。官方ISA+Xenia纠正wrapmask为64bit，低32返回0..3但rawr3可100000001，旧零扩展推断不能再用。197TU严格重建后实际推进826A9EC8原fatal。
- 82AC1DE8已strict重生、共同58166正文不改，197TU以/fp:strict全量重建并推进新原fatal。原float768差分Od/strict通过；rawO2的160内存差异保留。新profile禁止非strict对象，完整FPSCR硬件等价未证。
- 原21成员根与无IAT45秒对照均触发82AC1DE8 SDK原fatal；data_party_start原包已按整ISO/member hash追加，旧20根缺包AV保留。
- 原导入53 BL/8 API已核验；透明host IAT四导入跟踪已实际捕获同句柄创建、main Set/Clear、worker Set及main Wait返回0。有限采样不是死锁；close/reuse、非IAT/SDK内部调用和完整生产者图仍未知。
- Query kind1与实际Create请求kind0分开记账；不修改SDK、不用Query(state)消费信号，不把参数请求自动当backend模式实证。
- SDK真实presenter/隐藏HWND/UI loop保留，下一显示实验需正向swap/可见首帧证据；当前新阻塞优先按原叶边界/语义推进，不伪造事件唤醒。
- 61原44-byte体256后缀/状态差分通过，仅新增其hint；实际302非fallback目标全部mapped，但真实suffix/具体下游未记录，不等于302实现逐一验收。01旧模板变体仍待通用解析恢复。
- 新r6比较回调调查17sites/15targets均已映射；映射不代表逐个执行/完整语义验证。不要混淆GNatives与83250980另一尾分派表。
- 保留各旧fatal、缺包/GuidCache/TitleMap部署AV、合成harness页映射AV和旧61原fatal及当前等待边界；原数据/旧构建不改，不以空stub或吞fatal推进。
- 核验SEH funclet共享寄存器、异常路径和更多间接调用/函数边界；当前27case不覆盖全部58162函数。
- 明确SDK文件系统、两盘XEX/资源映射、系统服务、线程与初始化最早失败点，再考虑真实启动。

## P0：路线B实现映射与VM
- 继续补齐native名称映射未匹配项及零静态槽；vtable夹具已移除，区分真实标题初始化的注册效果与逐ctor执行证明。
- 将已定位PPC入口和路线B兼容实现分别记账；执行原生成Add代码不是已经重写/验证了3056项native兼容实现。
- 推进13731个动态名称/全局/委托调用点的类/继承/状态分派图；不得静态任意挑候选当resolved。
- 解析UProperty/参数布局，验证bytecode跳转目标/栈类型；设计带明确未实现调用诊断的最小VM或复用许可兼容实现。

## 本地化与游戏验收
原文实际加载分支、控制码、窄串编码、字体与TOC/副本回写仍需单文本PoC。
完整游戏链接、启动、首帧、输入/音频/战斗、保存/读取/换盘及通关均未验收；不把编译或静态图当可玩性。
