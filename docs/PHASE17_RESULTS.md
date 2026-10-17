# 阶段17：完整word-load叶与真实入口推进

## Verified：完整原范围与语义
新项目目录MagnaCarta2-Recompiled执行。原82B7CCD0..82B7CCD8完整8bytes（806300344e800020），SHA bbf1454f181f2d9d96316fad7d3c753d45df4678c1bafd0fe0217f84fa9b906f。
固定XEX/loader/展开像、前后各16bytes和全部44484条PDATA重新核验；该范围无包含PDATA。前非linkbranch、后不同序列、原只读两项指针及真实caller slot4C/LR支持完整叶边界；不把无PDATA本身当函数大小证明。
语义是EA=(原r3.low32+0x34) mod2^32，BE32读取零扩展到完整r3.u64；原blr不改LR/CTR，不写其它context或内存。r4=6不是本函数读取的参数；字段/对象名和标题实际读取值未知。
Windows物理bias是另一层：EA>=E0000000时host偏移额外1000；不要将guest EA wrap与host偏移混为一谈。

## Verified：1536例完整正常返回
14项新回归与独立byte-memory oracle通过；真实原样生成body/真实SDK宏1536例全部compile0/run0：128edge/random BE载荷×12地址布局。
包括随机upper-r3、低32wrap至0/4/30、阈值DFFFFFFC/E0000000及EAFFFFFFFC；后者需要4GiB+1000预留，八页全内存验证，不截断最后host页。
原BE载荷独立逐byte写入，physical bias独立计算再与真实宏核验，避免使用配套store造成同错抵消。
全GPR/CR/XER/FPR/FPSCR/vector/LR/CTR与host MXCSR比对，仅r3允许变化；八页无写且全部释放。
completed_without_fault仅在实际exit0、全部逐例记录和最终释放完整解析后为true。这里只证明有效、对齐、映射夹具完整返回；不覆盖fault/MMIO/未对齐/硬件所有模式，guest0合成页不证明标题空指针有效。
[研究](RESEARCH_WORD_LEAF.md)、[严格复现](EXPERIMENT_WORD_LEAF.md)记录精确命令与限制。badXEX实际exit1/无输出保留。

## Verified：严格生成和全模块真实运行
只新增8-byte入口hint，不改原SDK/原表/生成C++。397源新树628b54be3f51aa9f6ac198818102330a2e896a81765055f55a592c4144177f60。
58169共同body逐一不变，无删除；新增sub_82B7CCD0后58170函数/58416映射。分区文件变化不等于共同body变化。
197TU/58170函数静态审计零finding；197/197以/fp:strict全量重编译，再显式NOREF/NOICF无FORCE链接。新profile继承完整hint链和strict FP，未知树拒绝。
同一21原成员根/45秒/真实presenter/无hook：基线旧phase16模块82B7CCD0原fatal（C0000409/3221226505）；新模块推进到原82390A70常量写guest3，触发C0000005/3221225477，诊断CLI均exit0。
新阻塞不是另一未登记入口：原PDATA82390A20范围0x64，82390A6C为li r8,13、82390A70原91000003为stw r8,3(0)，直接绝对地址3。实际PE faultRVA06FA37C4的mov [rax+3],ecx与base100000000/r8吻合，LR82390A6C与原前call82870B78吻合。原显式fail-fast路径与实际fault已独立关联；不是普通对象null+字段store，也不是通过补hint就该继续的目标。
已定位exact native caller callRVA0641BDCF→06FA34F0，返回0641BDD4，与原824844F0 call/LR824844F4对应。原82484494读取BEword[r26]，824844A4与9E2A83C1 unsigned比较；相等跳过panic，非等路径落入本call。原常量及现有原Coalesced.int重新解析得到Core/Errors/BinaryFormat静态格式 `The file '%s' contains unrecognizable data`。
这是静态分支/格式来源，不是运行时最终message/filename/headerword捕获。忠实执行原store也不排除更早SDK、I/O或生成语义错误导致坏输入；缺WoodSword的因果关系尚未知。当前未部署资源、未添加trace、未修改fatal，异常保持原传播路径。
旧未登记fatal消失并进入原显式panic，不等于已记录本函数标题实际返回值或全部调用点验收。GPU depth target不是首帧，缺原WoodSword包仍是单独部署观察，未为推进本阶段增加资源。
AMD64 PE、197对象、全部58170函数map、三个host header快照及原299 indexed-native最终效果独立核验；该native效果不是逐ctor跟踪。
原SDK1193文件、14组2758对象与生成树、两张完整ISO重新hash不变。

## 失败、回退和交付
首轮word-leaf继承indexed-tail守卫误传当前profile，原字节预检明确拒绝；改为传固定indexed-tail，增加完整10项hint链回归。首次链测试把输出放在输入父目录下被overlap守卫拒绝，修正自制fixture布局而未放宽守卫；失败日志保留。
根698测试(skip2)和catalog通过；隔离源码676→698→恢复676(skip3)，原199文件hash恢复/新增6文件移除，主205文件保持修改态。
实际行为回退复用隔离恢复源码、旧phase16严格197对象、同一21原成员根，重现82B7CCD0原fatal；不改原资源、不删旧记录。
四件套及精确命令/input/literal output/exit位于ignored local/analysis/phase17/verification-release/；推送、远端HEAD、全新clone与四项CI另核验。
下一项先读取原panic message并追踪82390A20的真实caller及原数据条件，区分部署缺失/SDK兼容/原执行错误；不得跳过82390A70常量store或将其当新hint恢复；仍无正常标题关闭、首帧/输入/音频/战斗/存档/换盘或可玩性验收。

阶段17首个GitHub运行38981548880在Windows/Python3.12因hint-chain自制digest mock按未规范路径字符串识别SDK而失败，另一Windows矩阵被fail-fast取消；Linux两项通过。通过显式inputs/../inputs路径在本机复现同样exit1后，仅规范mock两端路径，保留路径别名回归；生产XEX/SDK哈希守卫、生成模块和真实运行输入不改。原CI日志和本机red/green记录均保留。

最终源码事务曾被外部上传程序新建的两个非UTF8 ISO进度sidecar中断；记录保留。仅新增对应进度元数据ignore规则，未读取/提交其内容、未移动或删除上传文件/原ISO，重新建立源码事务。
