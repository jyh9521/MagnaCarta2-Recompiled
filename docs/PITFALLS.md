# 调查陷阱与回归

1. Verified：本地起始只有通用模板，无 Git 元数据或测试；旧模板示例不是已实现功能。
2. Verified：同路径 default.xex 在双盘哈希不同；不能以大小相同推定可混用。
3. Verified：盘内无扩展名文件若直接对“镜像名::成员名”调用 suffix，会误认镜像后缀；已修复并加入回归测试。
4. 已避免：只看 .xxx 后缀就认定资源可解析；当前类型要求 magic，状态仍为 magic-only。
5. 已避免：把清单总字节数当磁盘占用；统计包含镜像与其成员，必须分开解读。
6. 未验证：UE3 Windows 可直接读取 CookedXenon、字体替换即支持中文、解锁帧率不影响逻辑，均不能作为工程前提。
7. Verified：GitHub CLI 未登录与 Git HTTPS 凭据是不同通道，发布状态须以实际 push/fetch 结果为准。

8. Verified：INT 后缀并不意味着实际内容为英语；本游戏 Coalesced.int 存在大量韩文文本。内容语言应按证据逐条确认。
9. Verified：大端长度字段下，Coalesced 宽文本和本游戏部分 UE3 FName 载荷是 UTF-16LE；盲目同端序解码会失败或乱码。
10. Verified：对既有 JSON 输出直接 write_text 会跟随硬/软链接并污染输入；本轮格式工具采用随机临时文件+原子替换，硬链接回归测试通过。
11. Verified：UE3 的 inventory、成员范围与哈希必须在 summary-only 分支也先校验；非空表不得覆盖 summary，避免接受恶形表。
12. Verified：路线 A 首轮严格分析在两条分支目标上失败；保留首轮日志，不能 force 或静默 stub 掩盖未解决调用。后续 hint 实验的结论单列。

13. Verified：仅增入口hint可生成但仍产生三条致命条件分支；原PPC证明根因是early-return切分，应该给真实完整范围，不能删REX_FATAL。
14. Verified：单TU成功掩盖5个SEH函数误合并；全模块首次真实192/197，PDATA边界修复后197/197。修复不能靠补空label。
15. Verified：CookedXenon仍可保留UFunction的ScriptText/CppText/Line/TextPos/FriendlyName，不按路径假定字段剥离。
16. Verified：446的ArrayFind无追加参数终止符，delegate comparison反而需要独立EndFunctionParms；两次真实失败报告保留。
17. Verified：顶层参数终止token误接受、UFunction小端profile未拒绝，均经独立审查修复并加实际入口链回归；不能以当前原版全通过替代坏输入测试。
18. Verified：全模块的inputs_unchanged涵盖明确已哈希输入，不涵盖未逐文件哈希的系统头与所有机器状态；隔离夹具成功不外推完整游戏。
## 第四阶段：不要混淆三种表或两种初始化

- `8320B5E0` 初被误认成 GNatives，按 203 个 native index 交叉核验出现大量冲突；它实际是 UObject vtable，不能以函数指针密集为依据当作 bytecode 表。
- 静态 `{UTF16BE name pointer, implementation pointer}` 查找表、UFunction.native_index 与运行时 GNatives 是不同证据。恢复前两者不证明最后一者已由原游戏初始化；本阶段随后实际执行两个原注册函数，但其vtable输入仍受控，不是完整startup链。
- 历史宿主构建成功后又修改宿主源，独立输入哈希复核正确失败。保留历史日志，冻结源码后在新目录重新链接，不忽略 source drift。
- SDK tool_mode 初始化不调用标题入口；真实 native 本体在合成 FFrame 中成功不等于 VM、UObject 世界、加载地图或图形运行通过。
## 第五阶段：部署、宿主配置与真实兼容缺口分开

- `RuntimeConfig.kernel_init`默认空；官方宿主使用`rex::kernel::InitializeKernel`。未配置时变量import descriptor `00010193`被误作地址，不能硬写伪指针掩盖。
- GetExecutableModule的object_ref若跨Runtime.Shutdown存活，历史诊断会在清理时AV；先释放该引用再关闭，保留失败原日志。
- 无audio_factory曾导致SDK音频对象空指针；无graphics消费者会使游戏在ringbuffer读指针固定时轮询。正式音频与真实GPU配置后这些早期阻塞已解除。
- 20秒观察结束不是死锁定位。三次栈/寄存器/原循环条件及读写指针观测才支持当时GPU等待结论，后续真实GPU执行又反证其并非永久游戏锁死。
- 缺TOC/Coalesced是局部部署问题，按原ISO成员哈希补齐后再找兼容缺口，不能用缺资产崩溃冒充最终成果。
- `xstart`是原82868EC0生成body，不是SDK替代函数；仅查`sub_82868EC0`会误判。最终真实fatal栈与linker map均覆盖原入口。
- 原SDKfatal fastfail未必经过VEH；额外只读日志sink记录fatal时PPC和调用栈，保持原abort，不以吞异常/返回成功实现“修复”。

## 第六阶段：发现hint不等于修复所有间接调用

- 原48-byte叶确实存在但不在PDATA内，地址由lis/addi构成；仅依赖PDATA/原始指针扫描会遗漏。增加版本锁定hint并严格重生，不填空stub。
- 独立叶harness初次在同一scope重复声明bool good导致compile1；完整失败留callback-generated-first，分scope并加回归后通过，未改生成体。
- 逐函数正文比较确认只新增1函数，不能只看TU数或codegen exit0推断其它函数未变。
- 新阻塞823C2740是虚分派尾调用thunk而非已证实的构造函数；它保留调用者LR，最近host符号不自动等于guest精确调用点。

## 第七阶段：子集扫描、部署和工作线程证据

- 精确4指令虚thunk扫描仅1个候选，不覆盖其他寄存器/比较回调，不自动批量hint。外部dispatch录制不是执行未知callee。
- 新代码通过旧阻塞后，6成员根缺电影/启动包而AV guest3；保留此部署失败，补齐18原成员后再认定真实兼容缺口。
- Movies/*.xxx探测失败不能靠空文件消除：原盘仅有对应bik。正式bik存在后继续保留原探测日志。
- 新fatal在工作线程，栈没有xstart/main。保留false观测flags，不用父线程历史证明冒充本线程栈证据。
- 下一比较回调原范围里有已登记尾块82C1C214，入口修复需验证多return和内部入口关系，不能盲目删除现存映射。

## 第八阶段：多return、位模式与筛选偏差

- C214只有原C208内部分支的有界引用证据；strict重生将其保留为内部label。不能只看函数总数不变就说没有修复，也不能手工删除尾块。
- -1的比较语义不等于64-bit全F；原rlwinm后真实r3.u64是00000000FFFFFFFF。CR6.SO/CA及相等return保持CA必须单独测试。
- 新mapping入口与内部label最初仅记录，review后加入硬成功守卫及负例；测试编辑曾IndentationError，原日志保留，修复后通过。
- 原18成员缺GuidCache导致部署AV；只增加hash验证原第19成员，不写空包/目录替代。
- 原native静态模板解析器以目标已generated-entry为前提，会遗漏真实已注册但尚缺入口的52；61另列为待调查缺口，运行时GNatives是独立见证。

## 第九阶段：合成地址空间与真实部署分开

- gateway初次harness在高guest地址AV：SDK原加载宏按REX_PHYS_HOST_OFFSET调整host页，初次只commit guest页。仅修正harness页计算/commit/snapshot后通过，不改SDK宏或原函数。
- 合成4GB reservation只commit五页20KB，执行后released=1；它没有加载游戏，不是原vtable/GNatives输入夹具，外部目标仅record。
- 19根缺TitleMap_MSPT导致AV guest3，保留部署失败；只追加hash验证原包到20根，不创建空map。
- 01模板遗漏是寄存器分配变体而非未生成；52/61旧entry筛选缺口与之不同。静态300/runtime302不意味着兼容实现完成。
- 61入口查找失败不等于它已消费下一byte；必须区分caller消费的61和handler将读取的新byte。

## 第十阶段：观测窗口不是故障证明

- 原61fatal消失后20秒仍运行，子进程诊断exit26，不是游戏正常退出，也不是父进程timeout124。
- 旧report曾因可选文件探测失败误称precede fault，但该run无exception/fatal；首次report/exit1保留。新增bounded_observation独立字段与负例，diagnostic_success/boot仍false，不吞fatal或改游戏。
- 三个相同等待采样与持续GPU日志并不证明死锁；无限timeout原静态链也不证明实际等待对象种类或生产者。
- 256后缀完全覆盖单字节输入，但仅在全合成16KB页执行原体并record尾目标；不是原游戏GNatives夹具或真实下游验收。
- unittest点名tests模块与直接执行local私有脚本分别遇ModuleNotFoundError；改用discover及根runpy入口，失败与修复命令保留。

## 第十一阶段：公共API、链接与弱观测

- 两轮standalone误用protected Window.presenter/HasSurface而编译失败，保留；只改用公共调用和诚实binding_requested，不放开访问权限。
- 标题首次新UI链接缺user32.lib而LNK2019/LNK1120，保留；加真实Windows依赖后成功，未用/FORCE或stub。失败还暴露partial host.map不含load base，解析器现仅在link exit0后解析map。
- 全树相等断言首次失败：397生成源同字节，只有codegen.d/stamp/build.stamp元数据不同；保留新输出/新hash，不复制旧stamp伪造可重复性。
- XEvent.Query(state)在发行DLL中Wait(...,0)后restore，会临时消费信号；只用type,nullptr。Query报告kind1不能提升为已验证backend reset kind，Initialize未见更新对应标志证据另存。
- 默认Windows缺PATH C++编译器时mock运行测试跳过，另在真实VS/Clang环境运行8项全通过；源码全测试的skip2与游戏验收分开。
- 探针窗口保持隐藏；SetPresenter无返回值，官方loop与零null日志都不是surface/首帧成功。标题exit26保持有界终止，不宣称完整runtime清理。

## 第十二阶段：观测器本身会改变时间

- 首次5.6MB非缓冲stdout dump使20秒探针实际44.523秒；期间真实缺包AV触发第二dump，两份交错/截断，拒作有效捕获，旧报告误称bounded也保留。
- 改为每次独立缓冲trace文件、原子status/fixed cutoff；fault输出stdout、SDK guest AV正见证覆盖窗口标签。清洁20秒run21.771秒，IAT指针/原页保护均恢复。
- 逐native PC重建58k符号索引导致报告后处理缓慢；预建索引保持nearest-symbol含义，不能把解析耗时算成游戏时间。
- FAULT快照无正常restore/freeze，不宣称capture_verified；blocked pre无post也不是死锁。原异常/fatal照常传播。
- NtResetEvent在固定DLL中不存在；KeResetEvent不同，不代填导出。原调用直接用host IAT，dispatcher SetFunction替换会漏direct calls；SDK内部/已缓存ptr仍非完整覆盖。
- SDK包装没有可推导完整unwind边界的研究失败、错误XEX拒绝、首轮trace失败均保留。

## 第十三阶段补充

- lfs/stfs不是直接memcpy：原顺序store可改变第二source，rawO2会消去回转，sNaN内存保持signaling但FPR0quiet；768夹具中160差异。显式/fp:strict后通过；不能泛称硬件FPSCR等价。
- FP缓存CSR与实际MXCSR必须一致初始化，host sticky flags不等于完整PPC FPSCR；不能为通过而拟合oracle。
- COFF弱alias section0不是函数定义；首次误读.pdata解码作废，最终锁定EXECUTE中的__imp__定义与对象hash。
- git show字节与Windows混合换行工作树不一定同hash；基线必须对照上一已验172hash，而不是默许EOL漂移。
- 文档读取显式UTF8；本次cp932读取失败保留，未据此改内容。

## 第十四阶段补充

- PPC64的rlwinm按ROTL32(low32)=rotate64(low32||low32)、MASK(MB+32,ME+32)；MB31/ME29跨64bit的mask为FFFFFFFFFFFFFFFD。原wordgetter低32为1时rawr3可100000001。原oracle误用32bit导致512 context失败，保留后按独立ISA/Xenia纠正，未改SDK。
- 原4C9A0020是bnelr CR6（BO4/BI26），不是beqlr；早return不表示函数结束，末尾mask和blr必须包含。
- 低32返回式正确不等于完整GPR正确；需比较全context、SO/CR6及无写内存两页。byte/hash守卫通过不证明语义模型无误。
- 已有REA对XEX格式拒绝证据复用，本轮用固定原像decoder，不重复启动不支持的分析；官方PDF首次web获取失败而实际urllib成功的记录均保留。

## 第十五阶段补充

- 条件尾函数不是getter：object+108总先store，随后null return或nonlink tail；只测最终返回值会遗漏真正副作用。
- 原r9 full64掩码FFFFFFFFDFFFFFFF，低32 store为DFFFFFFF，不能把rawGPR错误零扩展或改变r11 full64对象地址。
- tail ABI observer必须在入口比对fullcontext及已写flags；它不执行复杂原callee，更不替代真实标题中的callee。
- 当前更远fatal栈未含826C9920，旧fatal消失不能被写成当次已执行/完整验证callee；GPU depth target创建不等于首帧。
- 原callee PDATAsnippet首次else32拼写导致SyntaxError，失败保留后纠正；不得把未完成研究当作原执行证据。

## 第十六阶段 — 2026-10-17

首次生成身份断言错误地要求无函数删除：旧DEC4其实是内部合法分支。必须独立验证边界/引用并逐字比较tail，不能凭总数加一判断。首次harness.lib位置编译失败保留；缺WoodSword包不是此次明确未登记fatal的已证原因。
[阶段16结果](PHASE16_RESULTS.md)。

## 第十七阶段 — 2026-10-17

word-leaf继承indexed-tail hint时必须向原字节守卫传indexed-tail，而不是当前profile；首预检失败与完整链回归保留。EAFFFFFFFC物理偏移超过4GiB，不能只reserve4GiB；BE载荷勿用被测load配套store初始化，避免同错抵消。无PDATA不是完整函数大小的独立证明。
[阶段17结果](PHASE17_RESULTS.md)。

阶段17首个GitHub运行38981548880在Windows/Python3.12因hint-chain自制digest mock按未规范路径字符串识别SDK而失败，另一Windows矩阵被fail-fast取消；Linux两项通过。通过显式inputs/../inputs路径在本机复现同样exit1后，仅规范mock两端路径，保留路径别名回归；生产XEX/SDK哈希守卫、生成模块和真实运行输入不改。原CI日志和本机red/green记录均保留。

外部云盘可能在原ISO旁创建非UTF8上传进度sidecar；源码清单必须排除这种私有元数据，不能将其送入文本diff/回退事务。阶段17保留该失败，仅加入精确扩展名ignore规则，不删除用户文件。

## 第十八阶段 — 2026-10-17

原formatter的4096是UTF16 units而非bytes；不要只截4096bytes。r1+58不是+88，formatter后的当前r4不是原filename，读取原保存变参。RPM跨noaccess本机实际0bytes；partial清理helper测试不等于真实API返回非零partial。捕获不改变原CONTINUE_SEARCH，故障后header不当compare瞬间原子证据。
[阶段18结果](PHASE18_RESULTS.md)。

阶段18协议解析必须在全部UTF16校验后赋text；decode_error与text同时存在会造成false-success，interior-NUL实际red已保留。相同原21根/旧host的首次rollback也出现更早read0043004E/LR823BF2B8；必须保留独立故障，不能只挑panic运行宣称确定性。

## 第十九阶段 — 2026-10-17

部署A/B必须使用完全相同EXE/SDK/GPU和单成员hash差异，保留每次native失败与实际资源回退；timeout/任意AV不是正向越过指定加载的证明。Windows设备名路径负例先red再补guard。坏CS指针类似UTF16字节仅指纹，不能当对象错用字符串的实证。
[阶段19结果](PHASE19_RESULTS.md)。

## 第二十阶段 — 2026-10-17

clrlwi生成可能优化为u32&1，严格body提取器若预期通用rotate必须fail-closed后独立核验再改测试模板，不改生成体。byte邻居after起点+12不是+8；byte无需word对齐。SDK导出定位合成fixture不等于真实AV复现；其它AV/LR必须早筛以免消耗目标观察预算。
[阶段20结果](PHASE20_RESULTS.md)。

## 第二十一阶段 — 2026-10-17

残留unregistered target/success不能压过timeout、任意AV或矛盾退出码；消息text必须与原UTF16 hex/count及完整filename一致。22/23原生exit均C0000005，但错误文件可逆改变才是本次干预证据。所有不一致记录保持unknown，不伪装推进。
[阶段21结果](PHASE21_RESULTS.md)。

## 第二十二阶段 — 2026-10-17

exit26是既有host有限观察终止，不能当guest正常结束或任意timeout推进。原panic可逆消失不等于下一fatal已定位；故障分类器仍unknown，不为了结果放宽守卫。
[阶段22结果](PHASE22_RESULTS.md)。

## 第二十三阶段 — 2026-10-17

零delay调用持续返回不等于死锁；CS owner是guest KTHREAD pointer非thread ID，+10 atomic为native LE。稀疏桶/非原子字段/槽溢出/weak freeze不得夸大覆盖。parser矛盾标记实际RED3fail后GREEN，旧报告字段别名演进明确留证，不静默覆盖。
[阶段23结果](PHASE23_RESULTS.md)。

最终独立审计发现claimed桶全部截断、flags超宽/未知bits与post原参数矛盾可能误报capture；实际24tests/5fail RED保留，补每key已报告桶计数、低8flags和不可变参数配对守卫后24tests GREEN。首轮812测试事务及已恢复227源副本保留，最终817测试源码事务另存verification-final；既有真实raw重解析不得放宽。


## 阶段24：计数与真实回调
[阶段24证据与复现边界](PHASE24_RESULTS.md)：原计数加载0，实际callback持续完成队列项，711/709的余2仅为观察边界；不把晚期2>1采样当固定对象卡死。默认关闭透明RAW observer，保留原body、strict生成体、SDK与24成员资源根；早期AV未重现/未修复，exit26不等于首帧或可玩性。
