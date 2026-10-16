# 阶段7：虚分派thunk、原资源启动和比较回调缺口

## 已完成并验证

对阶段6实际到达的`823C2740`仅增加`[functions.0x823C2740].size=0x10`发现元数据。
strict codegen exit0、100.0s、397 written；197源/58,164函数静态审计0 findings。
逐函数比较只增加`sub_823C2740`，共同58,163函数正文全部同hash，0删除/0改变。
197/197 TU全量新编译、显式链接通过，58,410映射；独立AMD64 PE/map/对象归属核验通过。
原XEX、SDK、旧两组197对象及旧生成树不改；宿主C++不改，无静态vtable/GNatives夹具或替代函数。

真实原生成thunk的4组差分验证r10/r11/CTR/LR/r3及全部4096字节内存，compile0/run0，4/4通过。
唯一外部间接调用边界只记录目标，不执行未知callee；这不是外部实现兼容证明。
有限同模板调查要求执行section、精确四指令/寄存器、PDATA或前驱terminal、只读data指针引用及缺mapping，
仅得到1个候选823C2740，没有自动批量hint，也不声称覆盖所有遗漏。
细节与命令见 [虚分派研究](RESEARCH_VIRTUAL_THUNKS.md)、[生成实验](EXPERIMENT_THUNK_CODEGEN.md)。

## 实际原标题推进

- `boot-baseline`：旧阶段6构建本轮重现823C2740原fatal。
- `boot-thunk`：新构建通过旧阻塞，随后6成员根缺电影/启动包而AV，exit=`C0000005`、写guest3；完整保留，未当作最终兼容缺陷。
- 从原ISO显式暂存新18成员根：原6项、日志请求的8个启动包及4个bik，整ISO/逐成员hash全部验证；不存在的Movies/*.xxx不创建占位。
- `boot-staged`和`boot-independent`：新建宿主编译/链接均0，两次触发相同工作线程原fatal：

```text
[FATAL] Call to invalid or unregistered function at guest address 0x82C1C1A0
TITLE_FATAL_PPC ... lr=8286FE8C ctr=82C1C1A0
run exit=3221226505 (0xC0000409)
```

工作线程真实栈末端为`82BD2E20 -> 82C31FB8 -> 8286FD30 -> SDK fatal`，根部包含`8294CD98`。
该线程栈不含xstart/main，两项观测flags保持false，不用主线程历史冒充本线程证明；
此前6成员根的实际主线程故障栈另有原入口/main证据。诊断CLI exit0不代表游戏成功或正常Shutdown。

独立原像检查表明下一缺口是传入`8286FD30`的比较回调：原完整范围`82C1C1A0..82C1C228`为0x88，
无PDATA/入口mapping，但当前树已有内部尾块`82C1C214`的mapping。
原地址构造、r6参数、生成r25传递及实际`8286FE88 bctrl`/LR相互吻合；
比较回调本体尚未执行，不将其缺口误称为虚thunk、缺包或已修复问题。
下一阶段应验证双return/内部入口关系及原语义差分，再严格重生，不能盲目删除内部映射。

## 测试、回退和证据

源码基线393、修改态413、恢复态393项均OK（Windows symlink权限跳过1项），catalog通过。
隔离回退检查122个原源码hash及新增文件移除；主目录保持修改态。
恢复源码另配旧阶段6对象及同一18成员根重跑，验证旧823C2740原fatal恢复。
电影播放、可见首帧、地图/战斗/存档/换盘及可玩性尚未验收。

`local/analysis/phase7/`保留baseline/manifest、strict生成日志、新旧正文差异、197个编译记录、
`thunk-generated-*`及独立`thunk-independent`差分、所有`boot-*`失败与复测、`stage-root18.json`和新原资源根、
`next-blocker-*`原指令见证、两盘及SDK/591对象/三树身份核验。
`verification/`四项产物记录BASELINE/MODIFIED/ROLLBACK精确命令、输入、逐字输出、退出码及原hash恢复；
`boot-rollback`保留实际行为回退。原游戏数据、生成源、对象、EXE和完整日志全部ignored，不进入公开Git。
