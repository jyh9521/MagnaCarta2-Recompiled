# PreF_VJuto_Base2：单成员可逆部署实验

## Verified：版本、资源与唯一增量
新独立23成员根使用既有stage_runtime_files从固定Disc1整ISO重新hash后提取22原成员+一个PreF包。完整ISO SHA23e96219aa8b2116239c35e6f65013329bfd298d46a726edffa5224498028ac5，所有成员/重开输出hash通过。原22根、原ISO、原staging与历史记录不改，无hardlink/原数据替换。
新增`MC2Game/CookedXenon/PreF_VJuto_Base2.xxx`，offset3419625472，size1572864，SHA d5b57c3af82e17d6ad69478790d09a9b74d3cd55bba2a87639114c05285a22ca。原头9E2A83C1、BE446/25/header177867/4chunks的strict summary已独立重核。除根staging元数据外仅该一个新增文件，无共同文件修改或删除。

## Verified：真实22→23→22→23→22
复用阶段20已全量严格生成/197TU编译链接的固定EXE，SHA b85b36003ba546ccc0abd892a176939124513e25fedea4de6072af8f9e330e19；不是在每个样本重新链接。197对象、58171函数/58417映射、新树9f5eda2bd7aa3934a32187063b2365864f502927ed67984f3cc02fa740d8fee6及SDK1193文件重新hash核验。SDK e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a；GPU 0c23cfa23fc4fa5638dc8a3dc0de87b1041d97705d4677774083f1f350cd8d89。
同EXE/GPU复制到独立日志目录，child实际SDK/GPU加载路径与SHA核验；显式环境仅MC2_GAME_ROOT变化。panic与critical observer全程开启，原body/原vtable/GNatives/SDK不改。ASLR/线程调度/日志目录等仍不同，不声称全部运行状态确定。
五次顺序结果：

|样本|根|实际指定错误文件|原生结果|
|---|---|---|---|
|BASELINE|22|PreF_VJuto_Base2.xxx|C0000005 /3221225477，写guest3|
|MODIFIED1|23|voc_bt_juto_0.xxx|C0000005 /3221225477，写guest3|
|ROLLBACK1|22|PreF_VJuto_Base2.xxx|C0000005 /3221225477，写guest3|
|MODIFIED2|23|voc_bt_juto_0.xxx|C0000005 /3221225477，写guest3|
|ROLLBACK2|22|PreF_VJuto_Base2.xxx|C0000005 /3221225477，写guest3|

全部raw字段/完整UTF16BE消息/filename/保存原变参/headerword0与16零prefix独立核对，savedLR824844F4。原精确PE fault06FA8C14/894803对应原82390A70/91000003，完整panic与caller824844F0再次核验。资源根、EXE、GPU、SDK和所有parent输入前后不变。
新23根保持部署态，两次实际回退只切回未改22根；不删除新根或历史失败。不能只比较同为C0000005就认为无进展，关键是指定原message/文件名可逆变化；也不能把任意AV或timeout当推进。

## 因果结论及边界
本组单变量重复干预/实际回退支持：PreF缺部署是原指定panic的因果贡献因素，补部署使该首个错误可逆地推进到voc文件错误。它不是所有初始化/全部对象加载正确或零buffer唯一写历史证明。postfault内存读不是比较瞬间原子快照；线程/I/O顺序可能影响更早失败，不能推广成所有运行都确定。
新阻塞仍是原BinaryFormat fail-fast，不是新的未登记函数。voc原ISO成员offset3244447744，size491520，SHA be7f3f2f5f8c29fc14a152239d8102957a3a64ba6445c02c2748361f01570419；原头9e2a83c1001901be000072d100000005，strict446/25/header29393/1chunk summary通过。23根磁盘/staging/运行前后tree缺该文件。未部署voc；下一项需另建独立根做单成员A/B及回退，不将缺失与零头直接当已证唯一因果。

## 继续早期AV调查
固定observer源码与实际编译snapshot均be2f8eae789e70c62c6b445e234a6172b2751e0c969cd2fe24c8bf3b2891a2b3，SDK实际导出408F80/fault408F95/24bytes及原caller128bytes契约独立再次核对。五个child均有正确SDKattestation，critical flag1，独立解析与raw一致：5/5 not_observed，零CRITICAL行，全部实际故障都是WRITE guest3而非临界区READ。
本次没有新r29、入口对象+8、r11/r30或CS前缀读取证据，未重现/未修复先前坏CS指针AV，也未建立其资源因果。复用既有契约/fixture证据，不将重复合成fixture视为真实AV复现。

## 离线分类跨字段校验
deployment_evidence保持只读API，新增9test methods：真实RED22tests/26fail后GREEN22tests。必须让native退出C0000409、SDK corroboration/fatal stack/无AV及无timeout等字段一致；panic须C0000005/guest3 WRITE/SDK同故障、固定caller/完整UTF16BE hex/text/count/固定原formatter消息与同一filename一致。typed bool/int与run_record退出矛盾均保守未定；不靠残留target或success字段下结论。
原阶段19五报告重新核验保持合法分类，未为本阶段结果放宽。identity_verified仍默认False，仅由独立验证同EXE/SDK/唯一delta的caller显式担保后给有限关联；记录不是某条guest load读取整个包的实证。

## 复现
从原22根staging选全部原member，只追加上述PreF，使用`python -m tools.research.stage_runtime_files`输出到全新ROOT23；工具完整ISO/member守卫不得跳过。
```powershell
python -m tools.research.deployment_evidence --baseline-root ROOT22 --modified-root ROOT23 --member MC2Game/CookedXenon/PreF_VJuto_Base2.xxx --sha256 d5b57c3af82e17d6ad69478790d09a9b74d3cd55bba2a87639114c05285a22ca
```
真实入口沿probe_title_entry的阶段20固定profile，启用--capture-panic和--capture-critical-section。配对试验应先验证已有完整host-link/inputs manifest、同EXE/map/SDK/GPU，再复制同EXE到新日志目录并使用link_module.run_record；仅改变MC2_GAME_ROOT，保留每次原stdout/native exit和原输入前后inventory，重新链接另一个EXE不构成同EXE单变量对照。
完整精确执行命令、环境、raw、hash、独立原资源/AV/next-blocker报告保存在ignored local/analysis/phase21/；公共仓库只保存工具、测试及研究，不提交原资源/生成代码/二进制。
