# 阶段15：原写入、条件尾ABI与下一原阻塞

## Verified：完整原范围和写入顺序

原826A9EC8..826A9EE8完整32bytes SHA8b4df364b42994f970049966b3a8c5db4528bc3c6a18c3f7cd2a78b35d0501a7。
固定XEX/loader/展开像、前BCTR/后BLR、无包含PDATA和终止非link branch均独立核验；不在beqlr前截断。
原体先读object+0x108，保留full64 object到r11，再读member+0x80到r3；PPC64环绕mask生成r9，CR6比较member，随后总是写回object+0x108。
低32写入值=flags & DFFFFFFF；完整r9按FFFFFFFFDFFFFFFF掩码，不错误零扩展。
之后null条件beqlr返回，非null直接尾分派826C9920；原范围不写LR/CTR/SP，r4等原参数保留到tail边界。

真实callee826C9920已在原PDATA/生成mapping中：原0xCCC/3276bytes SHA0c364c3eb8f13c48fe278cb8e80b77c7a051fd53ba68b691b5f5e6eac9a726eb。
它包含栈帧、FP/GPR保存和多次写入/调用，不是可用空函数替代的终点。未凭猜测对象布局伪造callee执行。

## Verified：真实生成body的2560差分，明确边界

原样body、真实SDK宏、/Od /fp:strict compile0/run0，2560全部通过：
- 512例null：完整执行原体及真正条件返回；4byte写入仍必须发生。
- 2048例非null：仅观察外部直接tail ABI边界，未执行原callee。observer在tail入口立即复制完整PPCContext并读写后flags，证明store先于分派，不只比较最终状态。

完整context覆盖raw64 r3/r9/r10/r11、CR6/SO、LR/SP/r4/CTR、其它GPR/FPR/FPSCR/vector；两页8192bytes仅允许原flags4bytes变化，hostMXCSR也不变。
字段名flags/member只是fixture标签，不推断类、枚举或业务意义。
11项标准库回归通过；真实badXEX实际exit1且无输出，失败记录保留。独立边界与复现见[研究](RESEARCH_CONDITIONAL_TAIL.md)、[实验](EXPERIMENT_CONDITIONAL_TAIL.md)。

## Verified：严格生成、全量链接与真实入口

仅新增该真实入口hint，SDK/原XEX/生成C++/原表不手改。
严格生成397源，58168共同函数正文不变，仅新增sub_826A9EC8；新树641f44328a77585a8d263988f24d6044dfb39f14cd9b2d57f0522fb717c4699f。
197源/58169函数审计0 findings，197/197严格FP重新编译，58415映射显式NOREF/NOICF链接，AMD64 PE/map逐函数及三个host header快照独立验证。
新profile继承strict FP元数据与每对象argv检查，未知树拒绝。原SDK1193文件、12组2364对象、全部生成树、两张完整ISO重新核验不变。
同一21原成员根未增加资源，真实标题未链接fixture observer，而是完整原callee和SDK：
- 基线旧phase14模块：826A9EC8原fatal，C0000409/3221226505。
- 修改新模块：82A3DEA0原fatal，LR82A2AC9C/CTR82A3DEA0，r3=4005EEFC r4=0，C0000409/3221226505。

当前栈含sub_82A2AC48/main/xstart，但不含826C9920或刚恢复的callback。因此只能证明旧fatal消失并到达更远位置，不能据此断言当次null/非null路径、真实callee进入/完成或所有callee语义通过。
已有GPU depth target创建日志不是swap/可见首帧证明。原299项indexed-native最终效果仍匹配，不是逐ctor跟踪。

## 下一项与未验证

82A3DEA0尚未添加hint/执行；原72-byte候选SHAda78cc530445e6be3717bc6cec9e6cf949e163d65dc481ee5d6f63d4648b708a、无PDATA，含低byte selector/count的unsigned bounds检查，非法路径返回full64 FFFFFFFF80070057；有效路径经表/对象vtable尾分派。
原caller82A2AC98经vtable+0x20，LR82A2AC9C；有效分支将原r5/r6/r7重排到r4/r5/r6，末尾经目标vtable+0x10非link分派。实际输入count、表与下一目标未知，不能因r4=0而认定有效或无效。下一项先验证完整范围、两条路径、raw64错误值、索引/参数重排、全部寄存器与tail ABI，再恢复。
这是明确未登记fatal，不是等待超时或缺包AV。原SDK已有未实现服务日志与全部失败均保留，不称已完成兼容。

## 测试、回退与交付

带SDK根目录641测试(skip2)与catalog通过；隔离副本/clean clone缺本地SDK为skip3，真实SDK差分另已执行。
源码623→641→恢复623，原184文件hash恢复、新增6文件移除，主目录保持修改态。
实际行为回退使用恢复源码、旧phase14严格197对象和同一21根/45秒present，无hook，重现826A9EC8原fatal；原资源不由回退脚本改动。
精确命令/输入/literal输出/exit和四件套在local/analysis/phase15/verification/；推送、远端HEAD、全新clone和CI分别核验。
badXEX拒绝及独立PDATA研究首次SyntaxError的记录未覆盖。原资源、生成代码、二进制与完整日志均只在ignored local。
没有首帧、正常标题关闭、输入/音频/地图/战斗/存档/换盘或可玩性证明。
