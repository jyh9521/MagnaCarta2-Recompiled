# 第十五阶段之后的实验门槛

## 已完成
三处条件分支、五组SEH边界均经PPC/PDATA证据修复；严格生成、独立静态审计、197TU全量Clang编译与两叶函数27输入差分通过。
七包12901个UFunction完成字段/native index/flags和token framing；缺口统计不等于native实现恢复。
197对象显式宿主链接、SDK tool_mode初始化、58408映射/内存往返释放/关闭通过；全模块真实Add native执行8组受控参数成功。
真实XEX装载后已移除vtable夹具；正式kernel/audio/input/GPU配置与小型原资源部署使标题进入main，8234FF10已由原版本入口hint严格重生并全量验证；823C2740已strict重生，比较回调C1A0完整恢复，C214保留内部label；52/61入口已严格恢复；同一20成员根接入真实presenter/隐藏窗口；等待元数据已观测为Event，旧61 fatal消失。

## P0：路线A宿主链接与运行时初始化
- 首先独立验证82A3DEA0原72-byte候选（SHAda78cc530445e6be3717bc6cec9e6cf949e163d65dc481ee5d6f63d4648b708a、无PDATA）：实际LR82A2AC9C/CTR82A3DEA0，r3=4005EEFC/r4=0；原低byte selector/count的unsigned bounds检查、非法full64 FFFFFFFF80070057返回、有效表/vtable尾分派均需完整验证。不能假设selector0有效，先核验边界/两路径/参数重排/寄存器/tail ABI再hint。
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
