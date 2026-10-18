# 02_village_ter01：独立部署、完整解压与实际回退

## 目标与固定输入

当前工程优先级为首个场景、移动、完成一场战斗，汉化后置。本阶段只干预`MC2Game/CookedXenon/02_village_ter01.xxx`存在状态，不改原游戏代码、SDK、host、返回值或panic。阶段33的`root-cinook`作为基线，普通复制到`phase34/root-terrain`后仅追加该原成员；共同文件完整SHA256相等，不使用hardlink。固定EXE SHA256 `576e9324800b537e6713f457a34cc943a9ee97fcd21b7ae889f78dab2835c77c`，XEX、链接输入、SDK、生成树与197对象前后复核。

先完成基线单元测试，再串行执行所有游戏进程；固定25秒START、32秒A、45秒窗口。自动输入不等同物理手柄验收。本轮检验三个假设：缺部署可逆控制指定panic；原包结构/压缩异常；movie observer影响失败路径。多变量部署或抹去失败不属于本轮证据。

## 原成员独立校验（Verified）

Disc1完整SHA256 `23e96219aa8b2116239c35e6f65013329bfd298d46a726edffa5224498028ac5`校验后，从offset1911351296提取4915200字节，再开文件核验SHA256 `08d0cded71cbaeb2c604934b93c951b92df0a7780f356cdd38831a46591777f5`。UE3大端446/25，432 names、36 imports、138 exports，LZX标志4，12段物理区间全部在原成员范围内。

除了30013字节逻辑header及名称/导入/导出表验证，还通过固定libmspack桥接解压全部12段，恢复10505896字节逻辑地址空间；逐段长度与SHA256记录在`full-decompression.json`，全部export serial range经过表解析器检查。该结果排除本次严格解析与解压覆盖内的结构失败，不证明对象载荷语义、运行时反序列化或整个地图加载成功。未输出重建游戏包。

## 串行交叉与删除回退

| 样本 | terrain成员 | 原panic指定文件 | 原生退出 |
|---|---|---|---:|
| A1 | 无 | `02_village_ter01.xxx` | 3221225477 |
| B1 | 有 | `sizesmpl_structures.xxx` | 3221225477 |
| A2 | 无 | `未捕获，保持未决` | 3221225477 |
| B2 | 有 | `sizesmpl_structures.xxx` | 3221225477 |
| ROLLBACK | 无 | `02_village_ter01.xxx` | 3221225477 |
| A3 | 无 | `02_village_ter01.xxx` | 3221225477 |
| B3 | 有 | `未捕获，保持未决` | 26 |

A2缺失基线另以`C0000005`在`rexruntime.dll+0x117F11`读取host地址`FFFFFFFFFFFFFFF8`，两个线程记录相同IP，日志另观测guest LR `827B4C04`；未捕获指定panic，保持未决。该地址不是guest3写入，不能用相同退出码视为同一失败，也不能归因为terrain包。补充A3/B3不替换A2；全部样本保留于主汇总。

补充B3也记录SDK读取host `FFFFFFFFFFFFFFF8`的异常，进程最终exit26而非guest正常退出，没有指定panic；其逐异常IP、线程、SDK相对栈地址及寄存器原行保存在`unresolved-host-av.json`。日志多线程交错，不用相邻原行推定同一guest调用者或内存破坏源。两个组内均存在未决样本，全部样本汇总仍为false；仅有效指定panic子集的有限关联为true，不能替代整组结论。

全样本保守分类`limited_deployment_association=false`，完整样本不因无捕获而删减。修改根中观察到的明确后续包为`sizesmpl_structures.xxx`；缺包提示消失与正常加载完成分别记账。下一候选的库存记录保存在`next-member-inventory.json`，本轮未独立验证下一包部署因果，不把原`contains unrecognizable data`措辞直接解释为原包损坏。

实际回退先普通复制完整修改根，核验新增成员hash后只删除该成员，再逐文件核验恢复成基线inventory，最后以同EXE/同输入实际运行。主`root-terrain`仍保留新增成员。原始ISO和原构建保持不变。

## New Game与观察边界

| 样本 | movie采集有效 | prologue完整tick | 快照完整 | SDK readback |
|---|---|---:|---|---|
| A1 | true | 107 | false | `invalid_capture` |
| B1 | true | 136 | false | `invalid_capture` |
| A2 | true | 46 | true | `invalid_capture` |
| B2 | true | 125 | false | `invalid_capture` |
| ROLLBACK | true | 104 | false | `invalid_capture` |
| B3 | true | 111 | false | `captured` |
| A3 | true | 107 | false | `invalid_capture` |

有效电影采集逐项核对原open/CF0返回1、同对象句柄非零、text_count=1及完成tick配对。调用数不是视频帧数或单调加载进度。关闭`MC2_MOVIE_TRACE`的独立控制原生exit为3221225477，捕获文件为`..\MC2Game\CookedXenon\sizesmpl_structures.xxx`；该对照只涉及movie observer，不证明全部observer及调度透明。

首个场景加载完成、可见场景、移动、一场战斗仍待实际验收；序章视频/字幕渲染、电影正常结束、存档、换盘也未验收。历史阶段33的`C0000374`与早期critical-section AV保持未决，不由本轮未重现认定修复。所有SDK原日志、panic、快照、无有效readback与失败均保留。

## 失败记录与复现

首轮隔离回退准备在复制后误比较含不同root路径的完整inventory对象，断言失败，尚未删除成员、尚未运行游戏。失败日志`resource-rollback-first-failure.log`及复制根的identity记录保留；修正为比较全体相对路径与SHA256后重新执行，通过后才运行矩阵，不放宽内容守卫。

首版电影验证脚本把所有样本强制要求指定panic的SDK缺失行，遇到A2无panic时断言失败；修正为分别验证电影open/CF0/tick与可用panic的精确SDK行，无panic的A2仍未决。文档写入后的首次控制台打印遇到CP932编码错误，以显式UTF-8重跑，失败记录保持原文。

资源提取与单成员差异复用`tools.research.stage_runtime_files`和`tools.research.deployment_evidence`；固定运行参数见[阶段29](PHASE29_RESULTS.md)。精确命令、完整MC2输入环境、literal输出与native退出码、源码回退、清理与恢复、Git/CI身份写入ignored `local/analysis/phase34/VERIFICATION.txt`。四件套和全部原始失败留在同目录；Git只提交技术文档，不提交完整游戏文件。详细进度维护在[状态页](STATUS.md)，首页保持不变。

## 测试与收尾维护

基线与修改态均运行1223项单元测试，skip3；catalog和Markdown措辞校验通过。源码哈希守卫回退在隔离副本测试，原资源删除回退已恢复terrain原panic；跳过本机数据的测试不算游戏内验收。当前场景、移动和战斗仍待验收。

按活动构建输入追加保护`local/analysis/phase34/root-terrain`；本轮及恢复后再次清理共退休47份哈希一致重复输出，累计删除1163250948字节，含恢复后再次退休的4915200字节，不等同净节省。清除143份可重建Python字节码，释放2204261字节；后续测试产生的缓存另在最终完整性报告记录。

清理后选择性恢复原terrain成员并核验完整SHA256一致，再退休该重复副本。两张原ISO完整hash、活动EXE、SDK、生成树、197对象与当前资源根保持身份；全部唯一研究、原生失败日志与恢复keeper保留，兼容junction不移除。精确计划、报告、选择性恢复和最终Git/CI验证留在ignored `local/analysis/phase34/`。
