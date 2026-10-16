# 阶段14：双返回原叶、64bit模型纠正与下一原阻塞

## 原边界与两个return

原82AC2810完整32bytes SHA9174c77a101ea25e91a9fb0f1b8c9c7e512c4b7fdc7d80af0ce39fbfbe311f6a，
固定XEX/loader/展开像、前BCTR/后stw和无包含PDATA均独立验证。实际条件是bnelr CR6，不能当beqlr或在此截断函数。
只有该实际fatal目标被添加发现hint；SDK/原XEX/vtable/GNatives和生成C++未手工修改。

## Verified：一次真正失败与独立纠正

首轮真实生成body差分compile0/run1，2048例中512个完整context失败：原oracle把环绕rlwinm错误地限定为32bit。
原body对bit9=0/bit8=1返回rawr3=0000000100000001，并不是零扩展的1。
独立官方PowerISA的ROTL32/MASK定义和固定Xenia实现均说明：先复制低32为64bit，再MASK(MB+32,ME+32)，本条MASK63,61跨64位环绕。
因此低32返回(word>>8)&3仍成立，但完整r3不一定零扩展。按独立架构定义纠正oracle，不是修改SDK或为了拟合而放宽比较。
旧512失败、旧oracle/初版独立结论、原32bit假设和全部构建输出保留；字节身份证明不因语义推断错误失效。

新完整64bit模型实际2048/2048通过：early1024、late1024，compile0/run0；真实body始终同hash。
覆盖4相关bit组合/8背景/2 SO/16初始CR6/2地址，完整PPCContext、两页8192bytes、hostMXCSR均检查。
12项标准库回归通过，真实错误XEX实际exit1且不生成输出。边界、原指令、完整寄存器副作用与ISA引用见[研究](RESEARCH_BITFIELD_LEAF.md)。
不是物理Xenon执行验收，不能把低32表达式当完整原状态。

## Verified：严格全量构建和真实标题

strict生成397源；58167共同函数正文不变，仅新增sub_82AC2810。
树0144be8ebcfe91c81da80a8a370cb61d096b3cd2ee518117234ccc24cceb2256，197源/58168函数静态审计0 findings。
197/197 /fp:strict全量编译通过，58414映射显式NOREF/NOICF链接；AMD64 PE/map逐函数及3个host header快照独立复核。
新bitfield profile仍包含上一原float叶，故继承strict FP元数据和每对象argv守卫；旧profile保留回退。
原SDK1193文件、11组2167对象、全部生成树及两张完整ISO再核验不变；复用同一21原成员根，没有追加或伪造资源。

同一GPU+真实presenter/无hook45秒：
- 基线旧phase13严格模块：82AC2810原fatal，C0000409/3221226505。
- 修改新模块：826A9EC8原fatal，LR826A8158 CTR826A9EC8；r3=41DD8840 r4=7018F0A0。

这是明确未登记分派fatal，不是等待超时或缺包AV。旧fatal消失、新位置实际到达；未逐指令跟踪标题中的原叶调用，不能当所有路径执行证明。
原299项indexed-native最终效果仍匹配；SDK现有未实现服务日志不被隐藏，也不被称为已恢复。

## 下一项和未知

826A9EC8尚未添加hint/执行。原32-byte候选SHA8b4df364b42994f970049966b3a8c5db4528bc3c6a18c3f7cd2a78b35d0501a7，无PDATA，尾callee826C9920已在当前map中。原范围含object+0x108写入、object+0x80读取、条件返回和826C9920尾分派；不是只读getter。
下一项先独立核验完整范围、PPC64环绕mask、store先于return的副作用、null/非null路径、tail ABI和callee映射，再决定发现元数据。
原caller826A8154 bctrl经vtable+0x13C；对象含义和实际下游参数未验证。完整原边界/调用点证据保留在本地next-blocker-original.json。

## 测试、回退与交付

带SDK根目录623测试(skip2)与catalog通过；隔离副本/clean clone缺本地SDK为skip3，真实SDK差分另已执行。
源码604→623→恢复604，原178文件hash恢复、6新增文件移除，主目录保持修改态。
实际行为回退用恢复源码、旧phase13严格197对象和同一21根，重现82AC2810原fatal；原资源没有被回退脚本覆盖。
精确命令、输入、literal输出/exit及四件套在local/analysis/phase14/verification/；推送、远端HEAD、全新clone和CI分别核验。
原资源/生成源码/二进制/完整失败日志只在ignored local。没有首帧、正常标题关闭、输入/战斗/音频/存档/换盘或可玩性证明。
