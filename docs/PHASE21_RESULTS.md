# 阶段21：PreF原包部署与可逆真实入口因果验证

## Verified
独立23根只追加原版PreF_VJuto_Base2.xxx，整ISO/member/输出重开hash与strict UE3 summary通过；共同22资源不变，原22根保留。
同EXE/SDK/GPU，固定代码与观察flags，显式环境仅改MC2_GAME_ROOT：22→23→22→23→22五次真实入口。三次22根均原PreF panic；两次23根均推进原voc_bt_juto_0.xxx panic；两次资源回退都恢复PreF。原生均C0000005/3221225477 guest3 WRITE，凭退出码相同不能掩盖已核验文件名的可逆改变。
[完整因果/新资源/早期AV/复现](RESEARCH_PREF_DEPLOYMENT.md)。补部署对指定panic的因果贡献在本组受控样本成立，不推广为全部加载正确、唯一写历史或确定性启动。

## 新阻塞与早期AV
新voc原ISO成员hash和strict446/25/header29393/1chunk验证通过，但23根缺部署；原panic精确PE/原caller一致。下一步另建独立根部署voc并重复单成员实验，不跳过原fail-fast。
原临界区AV固定精确observer始终开启，五次均not_observed；没有新增r29/对象字段读取证据，未重现/未修复其上游成因。

## 构建、测试、回退与交付
资源变化不需要重新生成游戏代码：复用并重新核验阶段20严格生成树、197个strict对象及完整链接EXE/58417映射，避免改变配对EXE身份。不声称本阶段重新编译或链接197TU。
离线分类跨字段守卫新增9test methods，先RED22tests/26fail，再GREEN22tests；旧阶段19五个真实report重核仍分类有效。根779测试(skip2)、catalog、源码隔离770→779→770通过，恢复223原文件hash/移除2新增，主225源码保留修改态。
源码回退后另以恢复的分类器只读分析原raw/report，仍验证既有合法配对；实际行为回退已有两次同EXE资源根22回切，另在隔离恢复源码下重放22根真实入口恢复PreF原panic。所有native失败和测试RED保留，原23根仍部署态，无原资源/生成体/二进制入库。
四件套及精确BASELINE/MODIFIED/ROLLBACK命令/输入/字面输出/exit在ignored local/analysis/phase21/verification/。推送、远端HEAD、新clone与四项CI另核验。尚无首帧、操作、音频、战斗、存档、换盘或可玩性验收。
