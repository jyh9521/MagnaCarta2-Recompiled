# sizesmpl_structures：原包验证与独立部署实验

## 固定对象与证据等级

本阶段资源线只改变`MC2Game/CookedXenon/sizesmpl_structures.xxx`的存在状态。阶段34的`root-terrain`作为基线，普通复制到`local/analysis/phase35/root-structures`后仅补回该原成员；共同文件完整SHA256一致，不共享可写hardlink。固定EXE SHA256为`576e9324800b537e6713f457a34cc943a9ee97fcd21b7ae889f78dab2835c77c`，SDK、197个strict对象、生成树和链接输入继续核验，不因资源实验重编游戏。

优先级继续为进入首个场景、实际移动、完成一场战斗，汉化后置。SDK非法读取的独立分析见[输入SDK研究](RESEARCH_SDK_INPUT_AV.md)，其异常不作为本成员缺失或损坏证据。

## 原成员独立校验（Verified）

Disc1完整SHA256为`23e96219aa8b2116239c35e6f65013329bfd298d46a726edffa5224498028ac5`；成员在offset1858496512，物理长度5111808字节，提取后重新打开校验SHA256为`8f6c87ae07efb6a81799e0d364276fc22da1084c7f3fc4f2de6a7d3e6506935b`。

大端UE3版本446/25，725 names、67 imports、1140 exports；逻辑header为115723字节，LZX标志4。18个物理压缩区间全部在原成员范围内，通过既有固定libmspack桥接完整解压至16238476字节逻辑地址空间。逐段长度/hash及所有export serial range检查通过。此结论限定为严格解析和全解压覆盖，不证明对象反序列化语义、运行时加载完成或原包损坏修复；本轮未重建游戏包。

## 串行交叉与实际删除回退

同一EXE、25秒START、32秒A、45秒窗口；全部进程串行。自动输入不是物理手柄验收。

| 样本 | structures成员 | 指定panic | 原生退出 | SDK读回 |
|---|---|---|---:|---|
| A1 | 无 | `sizesmpl_structures.xxx` | 3221225477 | `invalid_capture` |
| B1 | 有 | 未捕获 | 26 | `captured` |
| A2 | 无 | 未捕获 | 26 | `captured` |
| B2 | 有 | 未捕获 | 26 | `captured` |
| ROLLBACK | 无 | `sizesmpl_structures.xxx` | 3221225477 | `invalid_capture` |

实际回退先复制完整修改根，核验新增成员hash后只删除该成员，再逐文件核验与基线相对路径/hash完全相等，最后使用同EXE/输入实际运行，恢复原指定panic。主修改根保留该成员。

全样本`limited_deployment_association=false`，指定阳性失败子集也为`false`：B组只有有限窗口与图像，没有明确不同后续panic；A2也未捕获指定panic。exit26既不是正常游戏结束，也不自动代表SDK AV。A2不删去、不以A1替换，不把“未捕获”写成加载完成。本轮未追加下一资源。

## 非黑读回与序章视频

B1的公开SDK读回为1280×720，921600个非黑像素，图像已实际查看。原`csm_prologue.bik`在10秒附近独立解码的画面含相同建筑、阶梯与守卫；8至13秒的150帧缩小采样比较最近帧RGB均方差为152.34。该数值不是原始像素相等证明。结合同对象原movie open/CF0返回1与持续tick，当前图像归为序章视频呈现证据，不是可操控的首场景画面。

A1/B1/A2/B2/ROLLBACK的prologue完成tick配对数分别为112/99/66/107/127；电影快照均未完整结束。调用次数不是视频帧数、单调加载进度或播放结束证据。B1图像、独立原视频参考、比较命令和原始PPM保留在ignored阶段目录，不提交完整游戏资产。

首场景加载完成、实际移动、一场战斗仍待验收；视频字幕排版、完整电影结束、存档和换盘也未验收。后续推进需要区分播放时长、后台加载及独立SDK输入并发故障，不为越过窗口改写原返回值或跳panic。

## 复现与失败保留

原资源提取、严格解析、完整解压、资源delta和保守分类复用既有`stage_runtime_files`、UE3解析器与`deployment_evidence`。本阶段只增加独立SDK诊断源和测试，不改当前游戏host/SDK。精确环境、命令、literal输出、原生退出状态及实际回退记录保存于`local/analysis/phase35/VERIFICATION.txt`；失败和准备错误保留于同目录，文档摘要不替代原日志。

关闭movie observer的A/B独立控制、SDK压力实验、测试和维护结果在本页收尾记录；详细阶段进度维护在[状态页](STATUS.md)，首页不追加阶段日志。

## 关闭movie observer的独立控制

相同45秒输入、同EXE下，仅关闭movie observer：A根恢复`sizesmpl_structures.xxx`原panic，B根出现`sizesmpl_plants.xxx`原panic，原生退出均为3221225477。该对照支持有限的指定失败差异，但不是原全样本矩阵的替代；B1/B2的无panic窗口仍未决。`sizesmpl_plants.xxx`只作为后续观察记录，本阶段没有独立部署该成员。

资源矩阵结束后才执行无游戏资源的SDK压力矩阵，压力矩阵结束后才执行movie-off A/B控制；三类结果分别保留。阶段35全量修改测试在后续SDK修复切换期间读到变化中的诊断源，出现旧锁合同断言错误；该运行保持失败，不作为收尾通过证据。阶段36在固定源码后重新执行测试、隔离源码回退、清理及CI。
