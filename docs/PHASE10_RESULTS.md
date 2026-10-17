# 阶段10：61扩展原入口恢复与真实等待边界

## 原语义、最小恢复和全量构建

基线同一20原成员根实际重现61入口的SDK原fatal，退出3221226505/C0000409。
原82517D70完整44-byte/11指令、原注册82E78008及caller82508228均独立锁hash。
它读取frame+12的下一byte，前移cursor，再保持LR尾分派GNatives[100+suffix]。
仅新增`[functions.0x82517D70].size=0x2C`元数据，原XEX/SDK/宿主C++不改。
strict codegen exit0（108.35s），397文件；197源/58166函数静态审计0 findings。
逐正文比较只新增该函数，58165共同函数全同hash，0删除/0改变。
197/197 TU重新编译与58412映射显式链接通过，AMD64 PE/map/全58166函数对象归属独立核对通过。
生成树固定为`bfb05b9fd7122d019d61d691c1764062107928d8262cc84dc4c3a4c8114e0121`。

真实原生成体在独立全合成稀疏4GB reservation中执行全部256后缀；compile0/run0，两轮均256/256通过。
32个64-bit GPR、LR/CTR、CR0..7、XER CA/SO/OV和16KB内存均核对，仅frame+12四字节cursor+1变化。
外部目标只record，不执行；全部4页释放，不加载原游戏，也不向真实标题写vtable/GNatives。
[原语义研究](RESEARCH_EXTENDED_NATIVE.md)和[可复现实验](EXPERIMENT_EXTENDED_NATIVE.md)保存命令。

独立只读原像核验60..6F全部16网关边界/注册；仅61旧缺mapping，不批量hint。
原页100..1FF的58非fallback与198fallback目标全部已mapped；本轮真实4096槽快照中302非fallback目标现在也全部mapped。
这是固定快照的地址闭包，不是所有handler执行、302兼容实现或VM完整性证明；实际61后缀/具体下游未采集。

## 真实运行变化，不把窗口当死锁

同一原20成员根复用，两次全新宿主均不再触发61 fatal，也未出现新的exception/fatal。
20秒诊断窗口后原主线程仍运行，采样3次后子进程按既有诊断路径exit26；不是游戏正常关闭或父超时124。
实际采样栈包含xstart/main，原链最近符号为：

```text
82E1F578 -> 82E1F528 -> 82E20F80 -> 82490300 -> 8248B100
         -> 82868B50 -> 82869B88 -> NtWaitForSingleObjectEx -> SDK/thread wait
LR=82869BC0; CTR=8248B100
```

原82869BBC为bl至xboxkrnl ordinal253导入，返回LR与现场一致；独立发行SDK导出表对应native等待栈。
原wrapper非alertable，上游传-1 timeout且原helper转换为NULL，是无限timeout等待静态证据。
**实际等待对象类型、唤醒生产者、是否正常主循环等待及与GPU呈现器的因果关系尚未验证。**
第二次运行SDK记录516次`IssueSwap: presenter is null`；当前明确使用headless/no-presentation配置，未有可见首帧。
不把相同3次采样或20秒存活解释为死锁、成功启动、地图渲染或可玩性。

首次运行helper exit1/旧report误把可选文件探测失败称为precede fault，完整结果保留。
只修正报告逻辑：`bounded_observation=true`独立于`diagnostic_success=false`、`game_boot_success=false`和`shutdown_verified=false`。
复跑helper0表示完整有界观测且身份守卫通过；实际子进程仍26，不改游戏/SDK或忽略fatal。

## 验证与回退

源码基线484→修改502→恢复484项均OK（Windows symlink权限跳过1项），catalog通过。
隔离回退逐文件恢复146个基线hash、新增文件移除；主目录保持修改态。
恢复源码配旧phase9构建与同一20成员根再次重现61原fatal，实际行为已恢复；新生成树/构建保留。
原两盘全SHA、SDK1193文件、六组1182对象及对应生成树、strict输入hash再次核验不变。
全新远端checkout重复源码测试；远端HEAD与本地提交及4项CI结果交付时核验。

失败留档包括旧61fatal、首次观测误分类、两次私有Python入口ModuleNotFoundError；此前各阶段失败不删除。
`local/analysis/phase10/`保存原独立证明、256差分、strict/197TU逐命令与日志、两次真实观测、原输入身份、
源码事务和实际行为回退；`verification/`含MODIFIED_FILE.py、DIFF_FILE.patch、VERIFICATION.txt和可执行ROLLBACK.sh。
VERIFICATION保留精确BASELINE/MODIFIED/ROLLBACK命令、输入、literal输出、退出码和恢复行为；原资产/生成代码/二进制/完整日志ignored。
下一项是独立验证等待对象/生产者与SDK真实窗口/呈现器绑定，不跳过等待、不伪造事件或原表。
