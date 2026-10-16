# 原panic只读捕获合同

## Verified：原码与栈槽
固定原XEX与展开像沿用阶段17身份。原82390A20完整0x64 bytes SHA256 `2932a88df6610f3118c7865881ede2674e5b0ef04b8ed2817642406e76b407a4`；独立重新解析原formatter82870B78/82870A48，原4096计数是UTF16 code units而非bytes，上限8192bytes，终止符两字节。
原panic栈帧分配0x60。原saved caller LR位于故障时r1+0x58（不是0x88）；原第一个变参r4完整BE64保存在r1+0x78。只有实际savedLR等于824844F4才解释本caller字段。r26/r30的意义依赖原formatter正常返回、非易失寄存器约定与未发生栈破坏，不将其提升为全部深层callee的动态证明。

## Verified：真实入口的故障后观测
相同21原成员根、真实XEX/原生成模块/SDK/presenter运行，仍在原82390A70写guest3，C0000005。可选observer未修复、吞掉或恢复该fault。
运行时savedLR=824844F4，r1=7018F160，r26=40F82A40，r30=40F82A00。原message8327C318读取182bytes（含UTF16BE NUL），严格解码为：

`The file '..\MC2Game\CookedXenon\wp_Juto_st1_0_WoodSword.xxx' contains unrecognizable data`

保存的原r4=00000000410B6120，独立读取102bytes（含NUL）得到同一文件名。r30+E0的count=0x33、r30+DC指针410B6120也与之相符；不把formatter之后当前r4误当文件名。
故障后BE32[r26]=00000000，前16bytes全零。原82484494/A4的比较目标9E2A83C1和真实panic caller已核验，但这不是比较瞬间的原子内存快照，也不直接证明哪个读取步骤制造了零值。

## 实现边界
`src/host/panic_observation.h`只提供ReadBytes/ReadWord/ReadUtf16，无游戏地址、PPCContext写入或原表构造。VirtualQuery先拒绝guard/noaccess，ReadProcessMemory只读；检查guest/host溢出、4GiB+1000跨度、E0000000物理bias跨界。失败清空全部前缀；原UTF16只按0000终止，不做字符替换。
真实Windows独立harness通过51checks，输入逐字节相同，guard页保护不变；raw RPM跨noaccess在本机返回0bytes，不能宣称观察到非零partial。partial结果分类与清理另由原helper受控测试覆盖。API不保证线程原子快照、任意MMIO或所有异常处理器环境适用性。
宿主仅在显式MC2_CAPTURE_PANIC=1、原write guest3、LR82390A6C及17处装载原指令匹配时捕获；完整模块和XEX身份仍由既有profile/hash合同守卫。捕获前后PPCContext逐byte不变，原EXCEPTION_CONTINUE_SEARCH保留。
严格parser拒绝重复/畸形记录、长短不一致、错误UTF16、非终止/截断、word与原hex不符；默认关闭。CLI显式请求却未得到有效捕获时exit1，不以原诊断fault成功冒充捕获成功。

## 证据边界
实际message把WoodSword路径与本次panic直接关联，较阶段17前置缺包日志更强；部署缺失、原资源身份、SDK读取/错误传播和原加载逻辑的因果链仍须分别检验。未部署该资源、未改fatal、未新增入口hint，仍未到首帧或可玩状态。
私有原字节、完整日志、独立合同和资源核验仅保存在ignored local/analysis/phase18/；不提交原资源/生成代码/二进制。

## Verified：原成员与部署独立核验
原Disc1已固定索引offset4015128576处读取196608bytes，成员SHA256 `f3ffd312d751b85a5d2cd954ff42a51bc1c012dfb5f272db09a5adb92177f85e`与原inventory一致。前16bytes `9e2a83c1001901be00006e0700000005`，严格UE3 summary验证BE版本446/25、header28167、flags4/1chunk及物理/逻辑边界；未在此审计解压或执行对象。
本阶段只重读成员，整ISO身份复用此前全盘hash证明、当前大小与匹配成员hash，不声称本次重复全盘hash。当前21根磁盘和运行输入记录都缺该包，SDK两次NtCreateFile为0xc000000f且路径一致。
实际message把缺部署和本次panic文件名直接关联，强支持下一隔离部署实验；仍无原子I/O/写历史证明零buffer的唯一成因，不宣称原包损坏或修复已经完成。
