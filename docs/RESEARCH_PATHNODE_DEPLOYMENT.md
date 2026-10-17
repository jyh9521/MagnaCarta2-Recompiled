# Test_PathNode：单成员因果隔离与加载边界

## 固定输入与原包检查

本阶段只改变`MC2Game/CookedXenon/Test_PathNode.xxx`的存在状态，不修改游戏函数、断言、返回值、host、SDK或生成体。阶段30的`root-village`作为基线，普通文件复制为阶段31的`root-pathnode`，仅追加该成员；共同文件逐SHA256相同，不使用hardlink。完整修改根继续保留。

原Disc1完整SHA256为`23e96219aa8b2116239c35e6f65013329bfd298d46a726edffa5224498028ac5`。`stage_runtime_files`完整校验ISO后，提取offset1463150592、size131072的原成员，并重开核验SHA256：`27def0a9cce7fad5481e0416afc329d1f855871f9b0b7ab9257cbd3afff85626`。

**Verified：** 包头为BE UE3 446/25，header_size=353921，287 names、22 imports、4579 exports，LZX标志4；两个物理压缩范围通过边界检查，逻辑header独立LZX解压后名称/导入/导出表通过现有严格解析器。该结果不证明全部对象反序列化成功。

复用阶段29原诊断EXE，SHA256为`576e9324800b537e6713f457a34cc943a9ee97fcd21b7ae889f78dab2835c77c`；197对象及host链接输入重新hash，SDK、生成树和对象目录另行核验。选择性按阶段30清理报告恢复历史`phase29/serial-both/module_probe.exe`一份并确认与活动EXE同hash；交叉实验仍固定活动EXE，不把恢复动作混入资源变量。

## 串行干预与实际回退

所有游戏进程串行运行；固定25秒START、32秒A及45秒观察窗口，固定原SDK/GPU、XEX与movie observer。每次记录完整环境、EXE hash、资源根前后inventory、原panic UTF16、原调用点、异常与SDK日志。回退从修改根另复制，仅在核验hash后实际删除新增成员，再核验整根inventory等于基线并运行原EXE；不是只恢复源码或隐藏日志。

| 样本 | 新增成员 | 原panic指定文件 | 原生退出 |
|---|---|---|---:|
| A1 | 无 | `Test_PathNode.xxx` | 3221225477 |
| B1 | 有 | `02_Village_Collision.xxx` | 3221225477 |
| A2 | 无 | `Test_PathNode.xxx` | 3221225477 |
| B2 | 有 | `02_Village_Collision.xxx` | 3221225477 |
| ROLLBACK | 无 | `Test_PathNode.xxx` | 3221225477 |


**Verified（有限因果结论）：** 两轮A/B交叉及独立删除回退中，单成员干预可逆控制首个捕获的指定包panic；缺少该成员是这组资源根中指定panic及加载阻塞的贡献因素，补回后推进到另一包失败。该结论只覆盖这组固定输入，不等同于全部panic、黑场或早期critical-section AV的唯一根因；包的实际读取字节量未独立观测，未将缺失日志消失当作加载成功。

## New Game后的独立进展

全部五次movie采集通过格式/来源校验；原`csm_prologue` CF0返回1，原open成功，movie句柄非零，伴随文本count为1。仅计同对象、CF0返回之后的完整tick前后对；各tick返回1且句柄非零。

| 样本 | prologue完整tick | movie快照完整 | SDK readback |
|---|---:|---|---|
| A1 | 23 | true | `invalid_capture` |
| B1 | 52 | false | `invalid_capture` |
| A2 | 22 | true | `invalid_capture` |
| B2 | 45 | false | `invalid_capture` |
| ROLLBACK | 22 | false | `invalid_capture` |

补回成员后的包名推进是主要证据；本组tick数量不构成单调进度指标。

后续明确失败为`MC2Game/CookedXenon/02_Village_Collision.xxx`，SDK记录精确路径`NtCreateFile`失败`0xc000000f`。当前修改根中该成员仍缺失。Disc1库存列出该下一成员offset1933305856、size524288、SHA256 cd5911bd882b562bcfaeee25c90cf3aa2fe682e52b723995bfea8833e47697f1（仅库存身份）。本阶段不追加第二个成员，也不把库存存在视作其因果验证。没有验收可见电影、字幕渲染、正常电影结束、地图加载完成或玩法；原生失败与`invalid_capture`均保留。弱快照未闭合不等于死锁，完成tick数量不等于电影播放帧数。

## 复现与证据

提取命令：`python -m tools.research.stage_runtime_files --iso ISO --inventory INVENTORY --output NEW_ROOT --member MC2Game/CookedXenon/Test_PathNode.xxx`。单成员校验：`python -m tools.research.deployment_evidence --baseline-root BASE --modified-root MODIFIED --member MC2Game/CookedXenon/Test_PathNode.xxx --sha256 27def0a9cce7fad5481e0416afc329d1f855871f9b0b7ab9257cbd3afff85626`。ISO与库存从原始输入生成，不将完整资产提交Git。

诊断EXE使用[阶段29](PHASE29_RESULTS.md)的`probe_title_entry`构建配置；固定EXE后仅改变`MC2_GAME_ROOT`。原始失败、五次交叉结果、默认关闭控制、包检查、完整环境、因果解析、历史恢复、实际行为回退与四件套位于ignored `local/analysis/phase31/`。`VERIFICATION.txt`保留精确命令、输入、原输出、退出码、Git与CI核验。

## 默认关闭控制、测试与维护

同修改根、同EXE关闭`MC2_MOVIE_TRACE`后仍出现`02_Village_Collision.xxx`原panic，退出3221225477；该观察支持movie observer不是包名推进的必要条件，不证明全部调度无扰动。六次原生失败与所有原日志保留。

基线和修改态均通过1216tests，skip3；catalog与Markdown措辞校验通过。源码隔离回退另行执行全套测试，不等同于完整游戏行为回退。GitHub远端、四项CI矩阵与干净检出核验记录于本机验证文件。

阶段31收尾追加保护`local/analysis/phase31/root-pathnode`；退休23份精确重复二进制，累计删除字节数730131704（含恢复验证后再次退休的131072字节，不等同于净节省）；删除139份可重建字节码缓存，释放2170262字节。历史EXE选择性恢复1份并核验活动hash；本轮清理后另恢复1份原成员并核验SHA256，再退休其重复副本。原始ISO、活动EXE、修改根、唯一研究及失败日志保留，修改根仍部署Test_PathNode；实际删除回退恢复原Test_PathNode panic。计划、恢复与两次清理报告保留于ignored `local/analysis/phase31/`。
