# 阶段19：独立原资源部署与可逆真实入口验证

## Verified
新22成员根仅追加已验证原版WoodSword，整ISO/member/输出重开hash通过；原21根及历史研究不改。
同EXE/SDK/GPU、固定模块和显式环境仅改MC2_GAME_ROOT，按21→22→21→22→21真实运行。三次21根均原WoodSword panic C0000005 guest3；两次22根均推进未登记82E078C0/C0000409；两次实际回退都恢复原panic。支持缺部署对该panic的因果贡献，不证明唯一原因或全部加载过程。
[干预、早期AV与复现合同](RESEARCH_DEPLOYMENT_CAUSALITY.md)。

## 构建、测试与回退
沿用精确strict生成树与197对象并重新核验hash；原样host重新编译/全197显式链接，58170原函数/58416映射和SDK身份通过。不重复生成或编译未变游戏模块，不新增hint、stub、原表或fatal bypass。
新增部署证据工具13tests；根完整732测试(skip2)、catalog，以及隔离719→732→719、原211文件hash恢复/新增4文件移除通过。主215源码保持修改态；实际回退使用未改21根而非删除22根，两个资源根继续保留。
四件套、精确BASELINE/MODIFIED/ROLLBACK命令/输入/字面输出/退出值在ignored local/analysis/phase19/verification/。所有native失败、RED/GREEN和更早AV保留；实际诊断进程失败不是测试成功启动游戏。

## 下一阻塞与未结问题
下一真实阻塞82E078C0：原caller82D60BE4 bctrl/LR82D60BE8，来自global83263C68对象的vtable slot14C。目标原12-byte叶候选可静态解析为读取[r3+21AC]的byte再取bit0，尚未登记/执行，类/字段名未知；独立PDATA/前后边界/原只读ref已支持高置信12-byte范围；语义差分与恢复在下一阶段完成，不能把候选直接当已恢复实现。
更早AV精确定位SDK RtlEnterCriticalSection_entry读取坏CS指针+18，上游原对象字段+8再加4；本次五试验未重现，未修复/未证明资源因果。原对象地址/字段生存期/并发写历史仍待受限捕获。
无首帧、输入、音频、战斗、存档、换盘或可玩性验收。推送/远端HEAD、干净clone及四项CI另核验，不将公开CI当原资源实机测试。
