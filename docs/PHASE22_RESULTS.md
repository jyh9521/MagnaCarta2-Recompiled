# 阶段22：voc原包部署与有限运行边界

## Verified
独立24根只追加原voc_bt_juto_0.xxx，整ISO/成员/重开hash与strict UE3 summary独立验证通过。固定已核验阶段20 EXE/SDK/GPU在23→24→23→24→23真实运行；三次23根恢复原voc panic/C0000005，两次24根到45秒观察上限，线程仍running，host诊断exit26，无原panic/SDK guest fault/未登记fatal。两次实际资源回退恢复原行为，24根保留部署态。
[资源、因果边界与复现](RESEARCH_VOC_DEPLOYMENT.md)。补部署对指定panic在有限窗口的消失具有可逆因果贡献；故障分类器对bounded observation继续unknown，不标记为新fatal、死锁、首帧或可玩。

## 下一边界与早期AV
精确PE/原PPC/IAT采样涉及82869850调用82E8DF4C/KeDelayExecutionThread；第二运行另采样到正常CS等待/延时返回/普通计算，未见稳定单一阻塞；需要继续独立验证调度循环/条件。缺资源warnings和未实现文件查询保留，非确定下一fatal。原critical-section早期AV本组not_observed，无新对象来源/写历史或修复证据。

## 构建、测试与回退
资源实验不修改游戏/host/SDK代码，复用并重新核验严格生成树、197对象和完整链接58417映射，不重复编译改变配对EXE。根779 tests与catalog通过；源码隔离779→779→779，225原hash恢复/2新增移除、主227保留。恢复源码下实际重放23根再次恢复原voc panic。
原失败/exit26/精确输入输出、隔离回退和交付核验位于ignored local/analysis/phase22/verification四件套。测试通过后提交推送，远端HEAD、新clone779 tests及四项CI另核验；公共仓库只含源码与研究文档，无原游戏资产/生成代码/二进制。
