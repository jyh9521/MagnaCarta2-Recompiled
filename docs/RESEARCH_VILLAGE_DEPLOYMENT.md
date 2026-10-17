# 02_Village_Persistent：单成员部署与原panic隔离

## 实验对象和证据等级

本实验固定阶段29诊断EXE、原SDK/GPU、阶段28 strict生成树和197对象；不修改原函数、生成体、断言或返回值。实验只改变资源根中一个成员的存在状态。实际退出仍是原生失败，不等同于成功启动或玩法验收。

原Disc1完整SHA256为`23e96219aa8b2116239c35e6f65013329bfd298d46a726edffa5224498028ac5`。`stage_runtime_files`重新校验完整ISO、按库存范围提取并重开成员：

| 成员 | ISO offset | Bytes | SHA256 |
|---|---:|---:|---|
| `MC2Game/CookedXenon/02_Village_Persistent.xxx` | 1932683264 | 622592 | `e690c8fb93f1cf1ec6ec0e833e0fab00ae84c4a68f71a84f28e3c6d42d0bc3c3` |

**Verified：** 原包头为BE UE3 446/25，header_size=148138，991 names、158 imports、1488 exports，LZX标志4及三个物理压缩范围通过边界检查。独立LZX解压逻辑header后，名称、导入、导出表均经现有严格解析器通过。该检查不包括全部对象反序列化，不把故障后的零buffer视为原包损坏。

基线为阶段29的both根；修改根由普通文件复制得到，只增加本表成员。共同文件逐SHA256相同，没有hardlink。回退根从修改根另行复制，仅删除已核验SHA256的新增成员，整根inventory恢复基线。原根和原ISO保持不变。

## 历史恢复与独立身份校验

从上一轮清理报告按精确文件前缀恢复阶段29 `serial-both/module_probe.exe`，实际恢复1份文件。重开后SHA256与保留的当前EXE相同：`576e9324800b537e6713f457a34cc943a9ee97fcd21b7ae889f78dab2835c77c`。仅恢复所需成员，未恢复整套退休目录。生成树、197对象、SDK库存及host源文件重新校验；每次实验重新hash EXE并核验资源根未变。

## 串行交叉实验

全部游戏进程串行运行，同一个EXE直接启动，不按样本重新链接；固定25秒START、32秒A、45秒观察窗口及movie observer。确认实际出现`csm_prologue`调用，而不只依赖合成输入轮询。

| 样本 | 新增地图包 | 原panic指定文件 | 原生退出 |
|---|---|---|---:|
| A1 | 无 | `02_Village_Persistent.xxx` | 3221225477 |
| B1 | 有 | `Test_PathNode.xxx` | 3221225477 |
| A2 | 无 | `02_Village_Persistent.xxx` | 3221225477 |
| B2 | 有 | `Test_PathNode.xxx` | 3221225477 |
| ROLLBACK | 无 | `02_Village_Persistent.xxx` | 3221225477 |

五次均为原`C0000005`写guest3，且panic消息、UTF16文件名、原调用点和SDK故障互证通过；不是只检查某条日志消失。实际回退在另一个普通文件副本上删除唯一新增成员后运行，恢复原地图包panic；修改根保持部署状态。

**Verified：** 同EXE A/B/A/B/回退中，单成员干预可逆地改变了首个捕获的包panic。**实验支持的有限因果结论：** 缺少该成员是这组资源根中原指定地图包panic及加载阻塞的贡献因素，补回后加载推进到另一包失败。该结论不等同于全部panic或黑场的唯一根因，不覆盖旧早期critical-section AV；原包实际读取字节量未单独观测。

## New Game后的加载边界

A1/A2均观察到`csm_prologue`的原open返回1、非零`movie+0x50`句柄，CF0返回1；伴随文本容器count为1。限定同对象、CF0返回后的完整prologue tick前后对各4个。B1/B2对应20和22个完整tick，返回均为1、句柄非零；不是将logo/opening的全部tick误算为序章进度。

新增地图包后，后续原panic文件变为`MC2Game/CookedXenon/Test_PathNode.xxx`，SDK同时记录该精确路径的`NtCreateFile`失败`0xc000000f`。该成员在当前修改根仍缺失。原Disc1库存给出offset1463150592、size131072、SHA256 `27def0a9cce7fad5481e0416afc329d1f855871f9b0b7ab9257cbd3afff85626`；本阶段不追加第二个成员，也不把库存记录当作该包因果验证。

各故障样本均没有有效SDK readback，保留`invalid_capture`；未验收可见电影画面、字幕渲染、正常电影结束、地图加载完成或玩法。A2的movie采集校验有效但`complete_within_snapshot=false`，未将弱快照中未闭合调用认定为死锁。缺包警告中其它名称不自动提升为当前阻塞根因。下一独立门槛是`Test_PathNode.xxx`的单成员因果隔离。


## 复现和原始记录

提取使用`python -m tools.research.stage_runtime_files --iso ISO --inventory INVENTORY --output NEW_ROOT --member MC2Game/CookedXenon/02_Village_Persistent.xxx`；所有路径指向实体目录，输出必须新建。基线的其它成员保持逐hash相同。`python -m tools.research.deployment_evidence --baseline-root BASE --modified-root MODIFIED --member MC2Game/CookedXenon/02_Village_Persistent.xxx --sha256 e690c8fb93f1cf1ec6ec0e833e0fab00ae84c4a68f71a84f28e3c6d42d0bc3c3`核验唯一增量。

原诊断EXE由`probe_title_entry`按阶段29参数生成，保持默认关闭的observer开关契约；固定该EXE后只改变`MC2_GAME_ROOT`，显式保持其它环境参数一致。原始运行、解析器结果、单成员差分、历史恢复、身份校验、失败记录、源码/实际行为回退及四件套位于ignored `local/analysis/phase30/`。完整原游戏包、ISO、EXE、图像和对象表不进入Git。


## 默认关闭控制与失败保留

同EXE、同修改根另行设置`MC2_MOVIE_TRACE=0`实跑，仍是`Test_PathNode.xxx`原panic，退出3221225477，资源根未变。该控制支持observer开关不是这次包名推进的必要条件；不外推为全部调度无扰动。六次原生失败、SDK日志、movie原始流及解析记录全部保留；无有效readback和弱快照状态不删改。


## 自动验证与收尾

本阶段未修改运行时代码。基线与修改态全套均运行1216tests，均通过，skip3；catalog通过，全部公开Markdown由措辞校验器检查。实际行为回退与源码回退分开记录，原包和修改根不随源码回退删除。精确重复输出按完整哈希退休，原始失败日志和恢复报告保留。GitHub提交、远端校验及四项CI矩阵证据保存在本阶段`VERIFICATION.txt`。
