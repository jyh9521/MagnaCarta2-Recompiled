# SDK输入：共享调用门锁与进程级回退

## 目标与固定输入

本阶段只处理输入SDK的共享刷新并发。`local/analysis/phase35/root-structures`在实验前登记完整相对路径/hash，全阶段固定，不提取、部署、删除或替换任何游戏资源。首场景、移动和一场战斗继续作为实际目标，汉化后置；资源线结果不随本阶段修复重新归因。

历史A2/B3、独立SDK压力失败、原DLL导出/指令与上游来源见[独立非法读取研究](RESEARCH_SDK_INPUT_AV.md)。当前修复不宣称重建了历史全部写入轨迹。

## 最小改动

新增locale-neutral `input_call_gate.h`：一把共享递归mutex覆盖完整SDK输入API调用，不只锁合成driver。`input_serialization.h`在guest启动前，将当前host EXE的三项必需输入IAT槽替换为包装入口：GetCapabilities、GetState、SetState；若该host导入GetKeystroke，也使用同一把锁。包装使用原PPCContext/base、恰好调用原SDK入口一次，保留原结果和内存副作用，并在正常返回时恢复原SDK留下的errno/GetLastError。

门锁只改变调用互斥与时序，不实现RefreshDevices、不清理SDK对象、不修补字符串指针、不吞异常、不制造输入或正常返回。递归mutex允许同线程合法重入；计数器的peak是嵌套delegate数量，不自动等同不同线程并发数。独立fixture的非嵌套并发峰值应为1。

当前生成游戏实际导入前三项，没有Keystroke；首版要求四项全部存在，因此预检以exit47拒绝启动，尚未修改IAT、尚未启动guest。失败输入与日志保留后，将**仅Keystroke缺席**设为显式允许分支；前三项仍要求各一次，若Keystroke存在也要求唯一。未为通过测试而把未知/缺失必需入口当成功。

## 守卫与回退

`--serialize-input`及`MC2_SERIALIZE_INPUT=1`显式启用，默认关闭。标题工具核验固定SDK完整SHA256、固定object-flag-leaf生成树、197个strict对象、资源根与全部host header快照。IAT预检核对AMD64 PE、DLL名、每项唯一性、原函数指针、范围与页保护，完成全部预检后才进行owned-pointer交换；未知状态失败退出。

本修改仅覆盖经过当前host输入导入的调用，不是SDK所有直接调用者的全局修复。SDK DLL、生成游戏函数体、原XEX和资源均不改。门锁可能改变调度，有限未重现不证明所有并发问题消失。

运行时回退在新进程撤销开关，使用同一新EXE、同SDK、同资源及同输入；不在guest线程活跃时卸载入口。`RestoreInputSerializationBeforeGuest`只供启动失败回退或隔离quiescent fixture使用。源码回退在另一个复制工作树执行hash守卫恢复，主修改态保留。

## 自动与实际验证

原生header fixture已执行：四入口原delegate完整context/内存和errno/GetLastError对比，8线程8000次调用峰值1，异常继续传播且锁释放，9组无写入PE拒绝，真实只读页IAT交换/恢复及不覆盖非owned指针。夹具原文为`INPUT_GATE_FIXTURE delegates=8008 peak=1 guards=9 exception_unlock=1 actual_restore=1`。

独立SDK探针的串行分支改用**同一门锁header**；无锁分支继续调用同一真实SDK。新增门锁不接入资源验证脚本。完整游戏使用同新EXE的ON/OFF/ON/ROLLBACK_OFF串行交叉；关闭开关的样本、原生异常、无捕获和有限窗口全部保留，不替换为成功。

## 已保留的准备失败

首个CLI插入把开关放入必需参数循环，触发argparse重复选项；修正并验证help。一次修正命令误用baseline工作目录，随后以原manifest逐文件恢复完整309份输入hash，再重跑baseline；错误运行不作为通过证据。一次构建传入strict-codegen父目录，完整生成树守卫拒绝；修正为原manifest登记的generated/default-disc1后重新构建，不放宽hash检查。

首次输入IAT安装因缺少Keystroke导入拒绝启动，原样保留。第二版已完成同EXE的ON/OFF/ON/ROLLBACK_OFF交叉：四次均为45秒观察边界、native exit26，开启时peak1，关闭时包装调用计数0。两种状态均未捕获历史SDK异常，因此该游戏矩阵不证明历史故障已经修复。详细复核见下节；远程CI本轮未执行。


## 2026-10-18收尾复核

### 代码归属与实际构建

- 生成游戏C++位于ignored `local/analysis/phase28/strict-codegen/project/generated/default-disc1`，共197个TU；严格FP对象位于`local/analysis/phase28/module-object-flag`。本轮不编辑生成体、配置hint或原游戏函数。
- 兼容SDK位于`local/upstream/rexglue/sdk/win-amd64`；发行DLL沿用上节固定SHA256。上游输入源码保留于本地独立研究目录，不作为本项目原创代码。
- 项目自有host和诊断在`src/host`，编译、版本守卫及报告在`tools/research`；测试在`tests`。结构化译文与通用技术分离。
- 复核原构建登记的222份直接输入hash全部相同，包含197个对象。新目录重新编译host并链接全部197个对象：compile/link均exit0；运行到45秒边界native exit26。CLI整体exit1和旧`host_build_success=false`包含运行诊断判据，不代表link失败。
- 活动资源固定为`local/analysis/phase35/root-structures`；本轮未增加、移除或修改游戏资源。新实验及精确命令留在ignored `local/analysis/phase36-closeout`。

### 已验证的缺陷与修复范围

独立SDK并发程序不加载XEX，两个线程经公开GetState/SetState入口操作同一InputSystem。阶段35已经复现原DLL `117F11`读取异常；阶段36首组无锁样本还分别出现`C0000374`和`117F64`读取异常。三组加锁样本完成读写各10000次。故障输入、原生退出和源码对应关系分别保留，不能把所有故障归为同一条已捕获写入轨迹。

本轮同一SDK探针重新执行无锁→共享门锁→无锁→共享门锁；每线程10000次，name/guid长度8192。两次无锁样本均为60秒timeout/exit124，两次门锁样本均为reads/writes各10000、errors0、exit0。本轮未重现异常地址，timeout未取得挂起栈，不命名为死锁；有限串行通过不等于全局race-free。

最小修复保留为默认关闭的host IAT门锁：三项必需输入导入和可选Keystroke共享同一mutex，完整原SDK调用恰好一次。它只约束当前EXE经过这些导入的调用；其他SDK直接调用、驱动增删、Shutdown与重入路径不由该门锁覆盖。没有修改发行DLL，不能称为SDK内部全局修复。

### ABI与内存验证

真实header夹具使用与host一致的Windows x64/Clang/MSVC运行库，逐字节比较原delegate与包装的完整PPCContext及内存，额外设置非零高32位GPR、LR/CTR、CR6、XER和浮点位模式。64位客体寄存器不得在包装中按32位返回值重建；guest base仍按原指针传递，不把guest地址直接转成host指针。

新增原生断言验证SDK输入结构：state16字节、gamepad12、capabilities20、vibration4、keystroke8；核对state.gamepad偏移4、capabilities.vibration偏移16和keystroke.user_index偏移6。独立固定16字节向量核验BE packet/buttons及有符号摇杆字段。该检查验证已固定头与本机编译布局，不是全部发行DLL接口的二进制ABI证明，也不采用Windows原生XINPUT结构替代客体结构。

既有原生夹具还覆盖8线程8000次门锁调用、异常传播后解锁、9组恶形PE拒绝、缺席可选Keystroke、真实只读IAT页交换及原指针/页保护恢复。输入驱动内部锁只保护其自身快照，不能替代SDK完整调用锁。

已抽查的guest观测层使用32位客体地址、64位跨度算术、物理区额外bias、页保护预检及ReadProcessMemory；既有回归覆盖环绕、越界和partial-read清空。该结论不扩展为所有生成load/store或系统接口已经通过内存安全审计。本轮未发现新的可独立证实的字段偏移缺陷，不据此批量改结构或生成代码。

### 未决与下一项

历史负八读取的原对象身份与竞争写入历史、早期critical-section AV、历史堆终止仍未闭环。45秒内SDK图像读回不是可见窗口、电影正常结束、首场景移动或战斗验收。下一项单独工程任务为：在固定资源和同一EXE条件下，采集SDK输入刷新故障的同线程标识、同对象地址及写入轨迹，区分未覆盖调用者与其他内存破坏来源。

源码事务按阶段36原始309文件hash基线，在隔离副本执行基线、修改和真实脚本回退测试；主工作区及`MODIFIED_FILE.h`保留修改态。四产物及完整命令、stdin、原文输出和exit写入`local/analysis/phase36-closeout/source-transaction/VERIFICATION.txt`。本地测试与远程CI状态分别记账。

## 阶段37续查

[同对象输入并发调查](RESEARCH_INPUT_CONCURRENCY.md)新增固定原探针复跑、分worker有界API边界记录、Windows外部异常线程/寄存器/真实PE unwind栈和minidump。负八AV与堆终止分别关联同对象及调用入口，未采集首个破坏写入；生产门锁范围及默认关闭语义不变。有限回退与再次启用结果不替代历史故障因果闭环。
