# 阶段18：原panic实际文件名与header观测

## Verified
在新项目目录继续同一真实入口，不改变原21成员部署。独立原码/formatter/栈布局验证后，新增默认关闭的`--capture-panic`只读观察。实际捕获原BinaryFormat message、savedLR824844F4、原变参文件名`..\MC2Game\CookedXenon\wp_Juto_st1_0_WoodSword.xxx`及故障后headerword=0/16bytes全零。
原82390A70写guest3的C0000005/3221225477仍原样结束；CLI诊断exit0不代表游戏启动。未跳过fatal、未恢复异常、未改原vtable/GNatives或部署新游戏资源。
[原码与观测合同](RESEARCH_PANIC_CAPTURE.md)记录4096 UTF16 units、savedLR r1+58、saved原r4 r1+78以及非原子快照限制。

## 构建与完整链接
生成输入没有变化：复用阶段17已经严格生成且197TU全量/fp:strict编译通过的树628b54be3f51aa9f6ac198818102330a2e896a81765055f55a592c4144177f60与197对象，而非重复相同实验。重新hash核验SDK1193文件、历史14组2758对象/生成树和原生成输入；不声称本阶段重新编译了197个未变TU。
本阶段重新编译真实host，完整显式链接197对象，NOREF/NOICF、无FORCE；58170原函数/58416映射、AMD64 PE、四个host header快照及原299 indexed-native最终效果独立核验。299最终效果不是逐ctor执行证明。
同样资源根的baseline与modified均为原panic C0000005 guest3，修改仅增加捕获；输入/资源/SDK/既有对象不变。

## 测试、失败与回退
新增14项严格协议parser测试、7项通用reader测试。真实Windows native harness compile0/run0、51checks通过（逐字节输入不变、guard保护保留）；其它平台/未提供固定工具链的checkout跳过该可选真实内存测试，不当作通过实机验证。
根完整719测试(skip2)和catalog通过；隔离698→719→698及旧host实际入口行为回退见本地verification证据；原panic故障与全部先前失败记录保留。baseline/modified/rollback输入和字面输出、返回值、四件套位于ignored local/analysis/phase18/verification-final/。
回退只在独立副本恢复旧host/driver并移除新增代码；真实入口仍执行同一原panic但没有PANIC捕获标记。主目录保留修改态，原生成模块、游戏资源与历史研究不改。

## 下一门槛
原ISO WoodSword成员hash/UE3 summary及21根缺部署已独立核验；接下来用独立资源根验证部署差异和实际行为回退；若继续报错，再追SDK路径、读取结果/错误传播与原header初始化。故障后零header不等于原文件头为零，错误message不证明磁盘原资源损坏。
仍未验收首帧、可见画面、输入、音频、存档、换盘或可玩性。推送、远端HEAD、干净clone及四项CI在交付时另核验。

首次只读review发现interior-NUL协议消息在标记decode_error后仍残留text，可能错误success；新增负例实际复现red后，将text赋值延后至全部校验完成，success显式排除decode_error。14项parser回归及实际原捕获重解析通过，保留首轮review/red/green。
首次实际rollback使用原baseline host和同21根，却在更早823BF2B8/LR处读guest0043004E发生C0000005，而非原panic。该运行和断言失败完整保留；不把相同输入等同确定性线程调度/启动路径，不删除或掩盖不同早期AV。后续同源码输入确认运行单独记账：rollback-confirm重现原panic C0000005 guest3且捕获标记消失；205原文件hash与最终隔离回退副本逐一相同。这证明一次实际行为恢复，不证明启动路径确定性。
