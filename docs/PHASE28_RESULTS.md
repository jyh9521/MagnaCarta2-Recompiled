# 阶段28：恢复8233D3D8原读取叶与确认后黑场

## Verified：完整原范围与副作用
从固定原XEX重新解码，8233D3D8的完整12字节为816301bc55630ffe4e800020，SHA256=503327950481e96a1cd186562cf11bc48315b21d3b6aeae17d94b7ddd908dd30。三指令为lwz r11,0x1BC(r3);srwi r3,r11,31;blr。EA=(rawr3.low32+1BC) mod2^32，BE32零扩展至完整r11，完整r3返回word>>31的0/1；无写入，其余GPR/CR/XER/LR/CTR/FPR/FPSCR/vector与内存不改。字段业务名称仍未知。
该叶无PDATA记录/覆盖；邻接前16字节是另入口vtable+320尾调，后为零与地址样式数据，不把间隙/后续数据合入叶。44484条PDATA、6个.rdata引用、前阶段实际caller8252FA74/LR8252FA78/CTR均独立重验。SDK对>=E0000000地址的+1000 host物理映射偏移单独建模，不混入PPC EA语义。

## Verified：发现修正而非兼容空实现
唯一新增hint明确entry/size12；object-flag-leaf profile完整继承旧12个hint，原XEX/SDK执行文件与每段原字节hash不符即失败。真正执行strict codegen后，新树58172函数、58418项双映射；旧58171个完整生成体逐字hash完全不变，只有新增sub_8233D3D8及登记。未手改生成体、原vtable/GNatives或SDK。
197TU全部/fp:strict重新编译，控制流审计197TU/58172体findings0；实际全197宿主链接通过。新titleprofile仅接收测得的固定生成tree，仍允许历史profile用于回退，capture和strict FP允许表同步接线，不扩大旧native-probe的固定树合同。
原始生成体抽取后在真实SDK PCH、无宏替换情况下执行Od/O2各1536组（128个边界/随机BE32×12个EA），总3072组完整PPCContext/8页内存/MXCSR比较通过、compile/run均0并有完整末marker/释放证据。包含高r3、EA wrap0、最后对齐word及物理bias；仅是显式合法对齐页的合成差分，不覆盖故障/MMIO/硬件PPC或实际标题对象字段值。

## Verified：真实入口已越过旧fatal，尚未可玩
同一24成员资源根（另有原XEX）和相同START/A有限输入，原SDK确实收到A、原消费者存储0→255→0。新构建不再出现8233D3D8缺登记fatal，45秒仍运行并在诊断边界native26退出；bounded_observation=true不是正常guest关闭、完整boot或可玩性成功。没有为继续执行而忽略fatal或强改原返回值。
原SDK读回1280×720输出已成功捕获，原P6解码RGB全零，实际查看为黑场。原main/poll/render候选的时间轴仍有正常进入/返回，不因黑帧或等待采样就认定固定死锁，也不将本次SDK图像当可见窗口/实际DXGI呈现证明。标题对象上该叶的具体读值、直接进入/返回记录未专门trace；合成原body差分不构成该动态字段证据。
运行同时记录csm_prologue.txt、csm_prologue.bik及其他原资源缺失，但尚未单成员/电影状态因果验证；黑场、缺文件与新流程进展分别记账，不以文件名宣布根因或盲目部署。当前下一窄门槛是独立原电影/脚本加载条件及确认后的状态、缺资源影响，而不是假造新fatal。

## 回退、失败与边界
基线旧EXE、修改新EXE、旧EXE回退、新EXE重启、旧EXE再次回退使用同原资源根及相同自动输入；另恢复完整278文件原源码，使用旧严格生成树/旧197对象重新编译宿主链接并真实运行。原源码/旧生成profile和实际行为回退分别验证，主工作树保持修改态，不删除任何旧研究/构建。原失败C0000409及新诊断26不标记为游戏exit0。
保留原范围/PDATA报告、RED/GREEN、初次verifier元数据宽替换导致size误记的失败及修正断言、私有paired runner缺空格SyntaxError、全部编译/链接/原始运行与图像。新失败没有通过stub处理。源码隔离测试、实际行为回退、fresh clone和同提交CI分别核验；精确命令、输入、输出、exit、哈希及四件套见ignored local/analysis/phase28。
历史坏CS AV持续观察，未重现、未修复；原资源部署缺失、原执行证据、静态推断、合成验证和玩法验收不混称。未提交任何原资源、生成体、二进制或游戏图像。
