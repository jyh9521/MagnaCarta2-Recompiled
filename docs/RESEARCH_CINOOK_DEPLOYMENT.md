# CinookIsland_CompTuto_01：单成员干预、混合失败与加载边界

## 输入锁定与独立原包验证

阶段33只改变`MC2Game/CookedXenon/CinookIsland_CompTuto_01.xxx`的存在状态。阶段32的`root-collision`为基线；普通复制为`phase33/root-cinook`，仅追加该成员。全部共同文件逐SHA256相同，不使用hardlink；游戏函数、原panic、返回值、host、SDK、XEX、197对象及生成体均不修改。

完整校验Disc1 SHA256 `23e96219aa8b2116239c35e6f65013329bfd298d46a726edffa5224498028ac5`后，以offset1790470144、size196608提取原成员，重开核验SHA256 `ced2b832120442ba3e5531c3aabf774414df4de90ac88e1f152787e8ab6b782f`。**Verified：** 大端UE3 446/25，1117 names、189 imports、3286 exports，LZX标志4；四段物理压缩范围通过边界检查，解压后的281546字节逻辑header通过名称/导入/导出表严格解析。逻辑header大于物理成员不代表越界，应按压缩后的地址空间分别核验。表级验证不证明全部对象载荷正确或游戏反序列化成功。

固定阶段29诊断EXE，SHA256 `576e9324800b537e6713f457a34cc943a9ee97fcd21b7ae889f78dab2835c77c`。按阶段32清理报告选择性恢复历史`phase29/serial-both/module_probe.exe`一份，完整hash与活动EXE一致；仍运行原活动EXE，不将历史恢复混入资源变量。全部链接输入hash及SDK、生成树、对象inventory核验前后一致。

## 串行交叉与实际行为回退

固定25秒START、32秒A、45秒窗口和原SDK/GPU、XEX；自动输入不代表物理控制器验收。游戏进程全部串行；第一轮基线测试与部分初始运行有时间重叠，补充B3/A3/B4在基线测试结束后单独运行，不据此宣称调度无扰动。回退从修改根另复制，核验新增成员hash后实际删除，确认全根inventory等于基线，再运行同一EXE；主修改根保留部署状态。

| 样本 | Cinook成员 | 原panic指定文件 | 原生退出 |
|---|---|---|---:|
| A1 | 无 | `CinookIsland_CompTuto_01.xxx` | 3221225477 |
| B1 | 有 | 未捕获，保持未决 | 3221226356 |
| A2 | 无 | `CinookIsland_CompTuto_01.xxx` | 3221225477 |
| B2 | 有 | `02_village_ter01.xxx` | 3221225477 |
| ROLLBACK | 无 | `CinookIsland_CompTuto_01.xxx` | 3221225477 |
| B3 | 有 | `02_village_ter01.xxx` | 3221225477 |
| A3 | 无 | `CinookIsland_CompTuto_01.xxx` | 3221225477 |
| B4 | 有 | `02_village_ter01.xxx` | 3221225477 |

**Verified（条件性有限因果证据）：** 缺失根及实际删除回退均重现指定Cinook原panic；具有有效捕获的补回样本推进到`02_village_ter01.xxx`原panic。固定输入下，缺失对该指定panic具有可逆的因果贡献证据；不推广为全部加载失败的唯一根因，也没有独立记录该成员实际读取字节量。

B1以3221226356（`C0000374`）终止，无有效panic、movie快照或调用栈，保留为未决失败，不将未捕获解释为指定panic已解除。该状态在本机Windows SDK `ntstatus.h`定义为`STATUS_HEAP_CORRUPTION`；状态本身不定位破坏者、分配者或guest原因。本轮应用事件1000的限定检索无该EXE匹配记录，不据此推定系统没有其他记录。初始失败受并行测试负载影响与否未证。

全样本`causal-evidence.json`的`limited_deployment_association=false`，因为B1保持未决；另外单列已捕获正向失败的条件性子集，不从全样本删除B1，也不把子集结果表述为整组通过。新增两项合成回归测试确认`C0000374`及残留panic字段不会被分类成有效因果阳性。旧早期critical-section AV未重现不等于修复。

## New Game后加载进展

| 样本 | movie采集有效 | prologue完整tick | 快照完整 | SDK readback |
|---|---|---:|---|---|
| A1 | true | 62 | false | `invalid_capture` |
| B1 | false | 未捕获 | false | `invalid_capture` |
| A2 | true | 63 | false | `invalid_capture` |
| B2 | true | 94 | false | `invalid_capture` |
| ROLLBACK | true | 58 | false | `invalid_capture` |
| B3 | true | 97 | false | `invalid_capture` |
| A3 | true | 61 | true | `invalid_capture` |
| B4 | true | 106 | false | `invalid_capture` |

有效采集中，同一`csm_prologue`原open返回1且句柄非零，原CF0返回1、text_count=1；仅统计同对象、CF0完成之后完整tick前后对，tick返回1且句柄非零。tick数是观察窗口内调用数，不是播放帧数或单调加载进度。B1无采集时不推定电影未调用或New Game未进入。

补回样本的下一明确失败为`MC2Game/CookedXenon/02_village_ter01.xxx`；SDK同时记录其精确路径`NtCreateFile`失败`0xc000000f`。原`contains unrecognizable data`措辞不证明原包损坏。下一成员Disc1库存offset1911351296、size4915200、SHA256 `08d0cded71cbaeb2c604934b93c951b92df0a7780f356cdd38831a46591777f5`；本阶段只核验库存身份，未独立解包、部署或证明下一成员因果。其他文件查询失败及`NtQueryInformationFile`未实现日志仍保留，不任意指定其中一项为根因。

同EXE/修改根关闭`MC2_MOVIE_TRACE`的独立控制退出3221225477，捕获文件为`..\MC2Game\CookedXenon\02_village_ter01.xxx`。该对照仅检验本次包名推进是否依赖movie observer，不证明全部observer或调度透明。全部原生失败及SDK日志保留；未验收序章视频/字幕渲染、电影正常结束、地图加载完成或可玩性，未将无有效readback和未闭合快照解释为死锁。

## 复现与证据

提取：`python -m tools.research.stage_runtime_files --iso ISO --inventory INVENTORY --output NEW_ROOT --member MC2Game/CookedXenon/CinookIsland_CompTuto_01.xxx`。

单成员验证：`python -m tools.research.deployment_evidence --baseline-root BASE --modified-root MODIFIED --member MC2Game/CookedXenon/CinookIsland_CompTuto_01.xxx --sha256 ced2b832120442ba3e5531c3aabf774414df4de90ac88e1f152787e8ab6b782f`。

固定构建与诊断配置见[阶段29](PHASE29_RESULTS.md)，只通过`MC2_GAME_ROOT`切换部署根。原包表、全部交叉与补充样本、默认关闭控制、实际删除回退、SDK原日志、身份清单及四件套留在ignored `local/analysis/phase33/`。`VERIFICATION.txt`记录精确命令、输入环境、literal输出、退出码、源码隔离回退、Git和CI身份。原游戏资产不提交Git。

脚本准备首轮因默认CP932读取UTF-8而失败，改用显式UTF-8后重跑；失败摘要保留，未修改游戏输入。所有既有失败记录继续保留。

## 测试与维护

基线1216tests、skip3；新增两项堆退出分类回归后，修改态1218tests、skip3。源码隔离回退恢复1216tests、skip26；缺少本机研究输入的跳过项不作为原生夹具通过证据。catalog与Markdown措辞校验、干净远端检出及四项CI矩阵分别核验；实际结果记录于验证文件。

阶段33收尾追加保护`local/analysis/phase33/root-cinook`；退休25份哈希核验重复二进制，累计删除730918136字节（含恢复验证后再次退休的196608字节，不等同于净节省）；删除143份可重建字节码缓存，释放2196489字节。历史EXE按报告选择性恢复并核验与活动EXE同hash；清理后选择性恢复原Cinook成员，完整hash一致，再退休重复副本。原始ISO、活动EXE、当前修改根、唯一研究及全部失败日志保留，junction未移除；实际删除回退恢复Cinook原panic。新计划、清理报告及恢复证据位于ignored `local/analysis/phase33/`。
