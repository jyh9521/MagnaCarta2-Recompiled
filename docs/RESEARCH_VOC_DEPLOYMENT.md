# voc_bt_juto_0：单成员部署与有限观察窗口

## Verified：资源身份和唯一增量
独立24成员根只追加`MC2Game/CookedXenon/voc_bt_juto_0.xxx`；23根保留不改。staging重新验证整个Disc1 ISO SHA256 `23e96219aa8b2116239c35e6f65013329bfd298d46a726edffa5224498028ac5`、全部成员与重开输出。新增成员offset3244447744、size491520，SHA256 `be7f3f2f5f8c29fc14a152239d8102957a3a64ba6445c02c2748361f01570419`。独立重读原slice并strict解析BE UE3 version446/licensee25/header29393/1chunk，首16bytes `9e2a83c1001901be000072d100000005`。忽略根staging元数据后只有该新增成员，共同23文件无修改/删除。

## Verified：23→24→23→24→23
复用阶段20已严格生成、197TU全量strict编译/完整链接的固定EXE，SHA256 `b85b36003ba546ccc0abd892a176939124513e25fedea4de6072af8f9e330e19`。本阶段游戏/host/SDK代码不变；重新hash核验197对象、58171函数/58417映射、生成树9f5eda2bd7aa3934a32187063b2365864f502927ed67984f3cc02fa740d8fee6与SDK1193文件，不声称重新生成/编译。各child实际SDK/GPU路径、源/对象/EXE/map、资源前后inventory均核验；显式MC2环境仅根变量改变，panic和critical只读observer保持开启。ASLR、调度、日志路径并非相同状态。

|样本|根|字面边界|原生exit|
|---|---|---|---|
|BASELINE|23|原voc BinaryFormat panic，WRITE guest3|3221225477 / C0000005|
|MODIFIED1|24|45秒观察到期，标题线程仍running|26|
|ROLLBACK1|23|恢复原voc panic，WRITE guest3|3221225477 / C0000005|
|MODIFIED2|24|45秒观察到期，标题线程仍running|26|
|ROLLBACK2|23|恢复原voc panic，WRITE guest3|3221225477 / C0000005|

23根原完整UTF16BE message/filename、savedLR824844F4和原panic fault逐次核验。24根没有原panic、SDK guest fault或未登记fatal；`TITLE_WAIT result=2 running=1`后由既有host诊断路径`std::_Exit(26)`结束，不是进程超时被父进程杀掉，也不是guest正常关闭或exit0。24根保持部署态；两次切回23根均实际恢复原失败。

## 因果与分类边界
该重复干预支持：voc缺部署对本组指定原panic具有因果贡献，补部署使它在45秒观察窗口内可逆消失。它不证明包的全部语义/初始化均正确、永远不再panic或唯一写历史。现有deployment_evidence故障分类器把两次bounded observation保持unknown，`limited_deployment_association=False`；没有为了本次结果放宽fatal判定或把timeout/无错误当启动成功。有限窗口内的原panic消失和“推进到一个新确定fatal”是不同结论。

## 当前观察边界，而非已证死锁
新边界是仍运行的标题线程/有限观察。精确PE call与原PPC/IAT核验，采样涉及原82869850→82E8DF4C的KeDelayExecutionThread路径；不能仅用nearest symbol或多个短暂停线程样本宣称死锁。第二次运行的三个样本分别落在正常临界区等待、延时返回后及普通计算路径，未观察到稳定单一阻塞。正常CS调用的原822D2670/LR822D2674和r3=4000077C与旧坏指针00430036/旧LR823BF2B8不同，不是早期AV重现。首样本r3=0仅支持当次零延时，不代表后续全部延时参数。保留SDK缺资源和NtQueryInformationFile(XFileXctdCompressionInformation) unimplemented记录，它们不是已证下一fatal；图形pipeline创建也不是呈现首帧。下一阶段应独立验证原延时/调度路径及其调用条件，区分可进展循环、真实等待与尚未部署资源，保持原调度/事件语义，不强行唤醒或跳过检查。

## 早期AV与回退
精确SDK READ CS+18/LR823BF2B8 observer持续开启；本组实际未重现早期AV，没有新的r29入口对象/+8/r11/r30读取实证，也没有修复结论。沿用已核验原caller与固定SDK bytes契约，不以合成fixture冒充真实复现。
源码隔离回退恢复全部225原文件hash并移除2新文档，主227文件保持修改态。恢复源码下另实际重放23根，原voc panic恢复；资源回退并非只看静态diff。原失败及有限观察退出均保留，无原包/生成体/二进制入库。

## 复现
从23根staging选择全部原member，仅追加上述voc，使用stage_runtime_files输出全新ROOT24，必须通过整ISO/member守卫。
```powershell
python -m tools.research.deployment_evidence --baseline-root ROOT23 --modified-root ROOT24 --member MC2Game/CookedXenon/voc_bt_juto_0.xxx --sha256 be7f3f2f5f8c29fc14a152239d8102957a3a64ba6445c02c2748361f01570419
```
真实入口复用probe_title_entry byte-flag profile和完整host-link/inputs，固定45秒及两个observer，同EXE交错运行上述五根；保留link_module.run_record精确command、env、raw/native exit和前后inventory。完整可重放证据/失败/四件套位于ignored local/analysis/phase22，不能从公开checkout假定私有游戏数据存在。
