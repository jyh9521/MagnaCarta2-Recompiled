# 技术记录

## 证据级别
Verified：实际文件字节、工具输出与测试；High-confidence deduction：由格式资料支持的推断；Unverified hypothesis：待实验。
本轮没有运行游戏，不把资源签名和工具测试解释成原生移植成功。

## 已验证
两张 7,838,695,424 字节 ISO 均存在 XDVDFS 分区；目录与全量成员哈希见 RESEARCH 文档和本地 JSON。
第二阶段已验证两盘 XEX 执行身份及全部 17 个可选头；通用扫描器仍保留其原有固定头级别，专用解析器承担进一步验证。
两盘全部 4145 个 UE3 包的 name/import/export 表与表引用通过，包含可选 LZX 解码；不宣称对象载荷完整反序列化。
8 个 Coalesced 容器内存往返逐字节相同，原文候选和结构对照只保存本地。

## 工具与接口
`tools/inventory/scan.py` 0.1.0，标准库；目录/显式文件递归扫描、流式 SHA-256、XDVDFS 文件表遍历。
`tools/inventory/compare.py` 区分同路径同内容、同路径不同内容与单盘独有。
`tools/validators/validate_catalog.py` 检查本地化结构、稳定 ID、审核状态与基础保护 token。
JSON 清单不含源文或资源 payload；机器绝对输入路径不写进清单标识。

## 边界与后续
通用文件清单的 related_resources 仍为空、不替代专用 UE3 依赖图；后者已输出 root Package import 文件候选，不证明运行时闭包。
XEX 导入库元数据已解析；PPC 代码生成/编译实测见 EXPERIMENT_ROUTE_A，VMX128、ABI、API、Xenos、音视频与存档语义尚待运行验证。
UE3 头区 LZX、FName 和对象表已验证；第三阶段新增 UFunction flags/index 与字节码 framing，通用对象属性流、VM执行和资源回写仍未完成。
详见 `docs/FILE_FORMATS.md`、`docs/RESEARCH_XEX.md`、`docs/RESEARCH_UE3.md` 与双路线文档。
原始模板保存在本地 baseline 中，后续真实发现持续写入项目文档，而非仅保留聊天。

第二阶段完整验收与命令见 docs/PHASE2_RESULTS.md，格式实验分别见 RESEARCH_COALESCED、RESEARCH_UE3、RESEARCH_XEX。

## 第三阶段已验证
- early-return 共享块与 SEH funclet 两类函数边界错误已以原 PPC/PDATA 精确范围修复；原游戏字节/SDK不变，不删断言、不补空label。
- 独立模板审计从13项（3致命分支+10缺标签goto）降为0；真实Clang全量构建从192/197降错至197/197通过。
- 真实两叶函数以SDK上下文与内存宏编译/运行27组合成输入，和独立PPC oracle一致；唯一间接调用hook只记录目标，不执行callee。
- 七定义包12901个UFunction字段边界和字节码framing通过；native=3056（203非零index、2853零index），直接native调用点26117，final调用8375。
- virtual/global/delegate共13731静态调用点仍待动态绑定；native声明匹配不是已恢复实现。
详细来源、失败、输入身份与复现见 RESEARCH_BRANCH_FIXES、RESEARCH_UFUNCTION、EXPERIMENT_MODULE_BUILD和PHASE3_RESULTS。
第三阶段当时尚无完整宿主链接、运行时初始化、游戏启动或画面验收；其余函数与异常路径语义不能由两叶函数夹具外推。

## 第四阶段已验证
- 197 个已哈希 COFF 对象显式链接，禁止引用裁剪/相同代码折叠，不靠空导入 stub 完成链接。
- SDK tool_mode Setup 返回 0；58,408 个地址逐项 GetFunction 一致，分配/读写/释放与 Shutdown 通过。
- 独立读取最终 AMD64 PE 与 linker map，确认 58,162 个生成函数各自存在于对应对象，没有只链接抽样 TU。
- 原生名称表的结构/消费者、UFunction 声明与执行入口分别核验，详见 RESEARCH_NATIVE_REGISTRATION。
- 全模块宿主调用真实 Add_IntInt，原生成实现及原操作数处理器执行 8 组合成输入；Code 前进 11、结果/保护字/非易失状态均通过。
- 静态恢复312个表/2676项非零配对及299个原注册模板；203个非零index声明与名称入口、注册函数一致。
- 真实执行token 0x1D与index146的原注册函数及重入路径；GNatives由原代码写入，原静态vtable指针与相关页仍受控提供，不是完整游戏启动链。
本阶段没有调用 XEX 标题入口，没有完整游戏 VM、资源加载或图形验收。路线 B 的兼容原生实现缺口不因路线 A 调用原生成代码而自动消失。
## 第五阶段已验证

- SDK真实装载原XEX，security/basic映像20,119,552bytes；正式InitializeKernel使13个变量导入槽/50字节改变，其他字节零差异，原.data4,199,568bytes全同。PE SizeOfImage22,284,288不同义，.reloc仅部分在security范围内。
- 不再写原vtable/GNatives夹具；从真实装载数据执行两个原注册函数与Add8组输入，正常Shutdown通过。合成调用参数/栈仍明确保留。
- 原入口82868EC0映射真实生成xstart；静态CRT表2/2/3873非零项，299个indexed-native注册仅为第三表子集。
- 正式kernel/audio/input配置与GPU公开C ABI使真实标题线程通过原入口、CRT并进入main路径。当前采样GNatives299项静态目标全部匹配，但不是逐构造函数调用跟踪。
- 首当前兼容阻塞为SDK拒绝未登记guest回调8234FF10，实际ctr=8234FF10/lr=823B9B1C，对应823B9B18间接调用。原48byte叶范围存在、无登记/PDATA；没有添加stub或修改生成代码来掩盖。
- 所有早期部署/宿主配置失败分别保留，不把缺TOC/Coalesced、无kernel/audio或无GPU消费者的轮询当最终游戏兼容缺陷。
详细原始证据、例外与下一门槛见PHASE5_RESULTS、EXPERIMENT_XEX_IMAGE、EXPERIMENT_TITLE_ENTRY和RESEARCH_STARTUP_CHAIN。

## 第六阶段：8234FF10发现缺口已推进

原48-byte hash守卫后仅增加发现hint；strict重生增加1个真实函数，共58,163，旧58,162正文全部同hash。
197TU全量重编译/链接与5组原生成体完整受控状态差分通过；未写替代函数、原像或SDK。
原标题两次到达新823C2740虚分派thunk缺口，caller828C5060/LR828C5064；其16-byte原体没有PDATA/映射。
当前未执行其下游目标，不把诊断成功等于可玩性；见docs/PHASE6_RESULTS.md。

## 第七阶段：虚thunk缺口解除，比较回调缺口

原16-byte thunk823C2740以版本锁定入口metadata重生。共同58,163函数正文未变，只增加1函数；197TU全量编译/链接。
4组受控状态验证保持LR/内存并记录vtable+12目标，不执行外部callee；同精确模板/只读引用/边界/缺mapping候选仅1。
原标题从缺包AV推进到18原成员运行根，工作线程两次触发82C1C1A0原fatal；原caller8286FE88/LR8286FE8C。
它是比较回调而非同模板虚thunk；当前内部尾块82C1C214已有mapping，不将整个0x88原范围误认全缺失。见docs/PHASE7_RESULTS.md。

## 第八阶段：完整比较入口与native分派

strict恢复C1A0完整0x88范围，原C214内部tail不再单独作为函数；58163共同正文不变，总58164。
14cases核对32GPR64/LR/CR6/XER.CA/4096B，负结果r3为00000000FFFFFFFF而非64-bit符号扩展，双return均覆盖。
固定源码禁用了lis/addi回调扫描的证据与17个r6构造site的有限研究见RESEARCH_CALLBACK_DISCOVERY；不夸大GapFill精确原因。
19原成员运行根实际到达GNatives[52]的82509380尾分派缺口，原caller82517858/LR8251785C；302vs299清单差集保留。

## 第九阶段：真实52网关与61扩展入口

仅新增原82509380完整24-byte发现元数据，58164共同函数正文不变；197TU重建/58411映射通过。
原生成体4组分派差分保留SDK宏，32GPR64/CTR/LR/20KB合成页不变；只record未知callee，与原标题实验分开。
01旧模板漏寄存器变体；新mapping让旧模板恢复数仅+52至300，运行期302不变。
追加原TitleMap后真实到达82517D70，caller82508228/LR8250822C；61将消费下一byte，但本体/下游尚未执行。

## 第十阶段：61扩展入口和真实等待链

原61完整44-byte范围/原注册/调用点均锁hash；仅新增82517D70发现元数据，58165共同正文无变化，197TU/58412映射通过。
原生成体256后缀差分验证32GPR64/CTR/LR/CR/XER及仅cursor4B写回；合成未加载游戏，只record外部目标。
固定真实GNatives快照302非fallback目标均有mapping；这不证明逐handler执行或实现兼容。
同一20成员根两次不再触发61fatal，原主线程在20秒边界仍运行；LR82869BC0对应原82869BBC调用NtWaitForSingleObjectEx。
发行SDK导出表独立对应native等待栈；静态wrapper非alertable、上游-1 timeout转NULL，实际对象类型/唤醒生产者未知。
headless持续IssueSwap presenter=null，仅证明缺呈现器日志，未建立其与等待因果关系；无首帧或游戏启动成功验收。

## 第十一阶段：窗口契约、事件元数据和证据边界

独立SDK契约验证SetupPresentation必须先于SetupGuestGpu；SDL官方UI loop/Window.Create/Open/SetPresenter及Runtime context/window在Setup前绑定。
仅隐藏HWND已实测，SetPresenter是公开void调用，未读取protected getter或声称surface/swap成功。
真实标题20秒后仍运行；post-resume非阻塞锁+RAII引用观测确认Event类别、guest3007D018、alias1/unnamed/host0。
父工具先核验发行DLL精确SHA再attest；进程不自hash。只读Query(type,nullptr)，绝不调用Query(state)消费信号。
发行Initialize与Query字段关系存在疑点，kind1只作API报告，实际backend reset/signal/refcount/producer保持unknown。
headless对照514条presenter-null，接入presenter后0条且wait元数据相同，不建立因果或deadlock/首帧结论。

## 第十二阶段：原事件链与下一叶入口

8原事件导入/53直接BL及完整原PDATA范围hash通过；实际raw LR逐条匹配，未把SDK内部/缓存函数指针调用纳入完整覆盖。
仅当前EXE四个IAT槽受控替换，原SDK函数原指针exact一次委托；锁自由固定ring保存前/后参数、状态与有界native栈。
PPCContext/guestfixture/errno/LastError差分与指针+页保护实际恢复通过，SDK/XEX/生成源不改，未改原GNatives/vtable。
清洁20秒捕获3866记录、drop/pending0且IAT恢复；45秒FAULT快照独立记为weak/nonfrozen，不伪装已完整恢复。
候选F80000AC请求Create kind0/initial0，main Set/Wait/Clear、worker Set与后续main Wait成功返回均实际观察；signal/backend/lifetime仍不由参数或数值相关性单独证明。
补原data_party_start后trace与无hook同到82AC1DE8原fatal；原20-byte无PDATA叶范围已独立锁hash，未恢复该入口。

## 第十三阶段：原浮点叶与优化合同

82AC1DE8已按原20-byte边界严格重生；整数格式oracle与真实768夹具覆盖别名顺序/完整context/双页/MXCSR。
rawO2消去回转转换，160项sNaN内存差异；Od与O2strict均通过，通用编译固定/fp:strict。
最终197TU/58413映射标题推进82AC2810，原32-byte双return叶尚未恢复；r10/r11/CR6副作用须先验证。
[原语义与机器码](docs/RESEARCH_FLOAT_LEAF.md)、[结果与未知](docs/PHASE13_RESULTS.md)。
