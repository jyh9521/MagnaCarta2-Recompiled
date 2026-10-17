# 02_Village_Collision：单成员部署与可逆失败边界

## 固定输入及包验证

本阶段只改变`MC2Game/CookedXenon/02_Village_Collision.xxx`的存在状态。阶段31的`root-pathnode`为基线，普通复制为阶段32的`root-collision`，仅追加该成员；共同文件逐SHA256一致，不使用hardlink。不修改游戏函数、原panic、返回值、host、SDK或生成体。

完整校验Disc1 SHA256 `23e96219aa8b2116239c35e6f65013329bfd298d46a726edffa5224498028ac5`后，以库存offset1933305856、size524288提取原成员，重开核验SHA256 `cd5911bd882b562bcfaeee25c90cf3aa2fe682e52b723995bfea8833e47697f1`。**Verified：** BE UE3 446/25，header_size=108507，299 names、22 imports、1238 exports；LZX标志4，两段物理范围通过边界检查，逻辑header独立解压后名称/导入/导出表通过严格解析。表级验证不证明所有对象载荷反序列化成功。

沿用阶段29原诊断EXE，SHA256 `576e9324800b537e6713f457a34cc943a9ee97fcd21b7ae889f78dab2835c77c`。197对象和host链接输入逐hash复核，SDK、生成树及对象目录另核验前后inventory。按阶段31清理报告选择性恢复历史`phase29/serial-both/module_probe.exe`一份，完整SHA256与活动EXE相同；实验仍固定活动EXE，不将历史恢复混入资源变量。

## 串行交叉与实际行为回退

固定25秒START、32秒A、45秒观察窗口及原SDK/GPU、XEX、movie observer；所有游戏进程串行。每次记录环境、原panic UTF16/调用点、异常、SDK日志、EXE hash及资源根前后inventory。回退从修改根另复制，核验新增成员hash后实际删除，再核验全根inventory等于基线并运行原EXE；不是仅源码回退。

| 样本 | 新增成员 | 原panic指定文件 | 原生退出 |
|---|---|---|---:|
| A1 | 无 | `02_Village_Collision.xxx` | 3221225477 |
| B1 | 有 | `CinookIsland_CompTuto_01.xxx` | 3221225477 |
| A2 | 无 | `02_Village_Collision.xxx` | 3221225477 |
| B2 | 有 | `CinookIsland_CompTuto_01.xxx` | 3221225477 |
| ROLLBACK | 无 | `02_Village_Collision.xxx` | 3221225477 |

**Verified（有限因果结论）：** 两轮交叉及独立删除回退中，该单成员干预可逆控制首个捕获的指定包panic。缺失是这组固定输入中该panic和加载阻塞的贡献因素，补回后推进到另一指定包失败。该结论不是全部panic、黑场或早期critical-section AV的唯一根因；没有独立记录该成员的实际读取字节量，也不以缺失日志消失代替加载成功。

## New Game后的进展及下一边界

五次movie采集均通过格式/来源校验；同一`csm_prologue`原CF0返回1、原open成功、句柄非零、text_count=1。仅统计同对象且CF0返回之后的完整tick前后对；tick均返回1且句柄非零。

| 样本 | prologue完整tick | 快照完整 | SDK readback |
|---|---:|---|---|
| A1 | 48 | false | `invalid_capture` |
| B1 | 59 | false | `invalid_capture` |
| A2 | 48 | false | `invalid_capture` |
| B2 | 62 | false | `invalid_capture` |
| ROLLBACK | 48 | false | `invalid_capture` |

完成tick数是观察窗口内的调用数量，不是播放帧数或单调进度指标。补回后首个明确失败为`MC2Game/CookedXenon/CinookIsland_CompTuto_01.xxx`，SDK记录其精确路径`NtCreateFile`失败`0xc000000f`；原`contains unrecognizable data`文字本身不证明该原包损坏。下一成员的Disc1库存记录offset1790470144、size196608、SHA256 `ced2b832120442ba3e5531c3aabf774414df4de90ac88e1f152787e8ab6b782f`（仅库存身份，未独立解包或部署）；原记录见本机`next-member-inventory.json`，本阶段不追加第二成员，库存存在不视为下一成员因果验证。

同修改根及同EXE关闭`MC2_MOVIE_TRACE`后仍出现相同下一包原panic，退出3221225477；该对照支持包名推进不依赖movie observer，不证明全部调度无扰动。六次原生失败全部保留。未验收序章视频/字幕渲染、正常电影结束、地图加载完成或可玩性；`invalid_capture`及未闭合快照保持原记录，不将其推定为死锁。旧早期CS AV未重现不等于修复。

## 复现与证据

提取：`python -m tools.research.stage_runtime_files --iso ISO --inventory INVENTORY --output NEW_ROOT --member MC2Game/CookedXenon/02_Village_Collision.xxx`。

单成员差异检查：`python -m tools.research.deployment_evidence --baseline-root BASE --modified-root MODIFIED --member MC2Game/CookedXenon/02_Village_Collision.xxx --sha256 cd5911bd882b562bcfaeee25c90cf3aa2fe682e52b723995bfea8833e47697f1`。

固定EXE构建配置见[阶段29](PHASE29_RESULTS.md)，只通过`MC2_GAME_ROOT`切换资源根。独立原包验证、五次交叉、默认关闭控制、因果解析、New Game进展、原失败日志、历史恢复、实际回退及四件套保留在ignored `local/analysis/phase32/`。`VERIFICATION.txt`记录精确命令、环境、literal输出、退出码、Git及CI证据。原游戏资产不提交Git。

## 测试与维护

基线和修改态均通过1216tests，skip3；源码隔离回退同样发现1216tests，skip26；缺少本机研究输入的跳过项不作为原生夹具通过证据。catalog与Markdown措辞校验通过，精确结果另记录于验证文件。源码回退不代替上述实际删除成员后的行为回退；GitHub远端、干净检出及四项CI矩阵使用本次提交身份核验。

阶段32收尾追加保护`local/analysis/phase32/root-collision`；退休24份哈希核验重复二进制，累计删除731049208字节（含恢复验证后再次退休的524288字节，不等同于净节省）；删除137份可重建字节码缓存，释放2176985字节。历史EXE按报告选择性恢复并核验与活动EXE同hash；清理后选择性恢复原Collision成员，完整hash一致，再退休重复副本。原始ISO、活动EXE、当前修改根、唯一研究及全部失败日志保留，junction未移除；实际删除回退恢复Collision原panic。新计划、清理报告及恢复证据位于ignored `local/analysis/phase32/`。
