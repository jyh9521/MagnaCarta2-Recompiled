# 阶段11：真实presenter与等待Event元数据

## 身份和完整生成模块

原XEX、SDK和原20成员根不改，不增加资源/发现hint或手写原表。
strict codegen exit0；与阶段10比较397生成源全部同字节，仅3项codegen依赖/stamp元数据变化。
新树`8eff0b28ea7e74aada90e1e5f7802a34ed3b9ef7d30867c51bf64231bd573c32`单独精确allowlist，旧profile保留，未知树仍拒绝。
197源/58166函数静态审计0 findings；197/197 TU全量重编译/58412映射显式链接通过。
独立PE AMD64/map/所有58166函数与对象归属核对通过；两新增host header纳入hash与snapshot，SDK/工具/对象/游戏资源前后身份守卫通过。
原两盘全SHA、SDK1193文件、七组1379对象及其生成树再次核验不变。

## 最小独立presenter：Verified

依固定SDK公共头与随附官方应用，Initialize SDL context → SetupPresentation → Window.Create/Open/SetPresenter，
在Runtime.Setup/SetupGuestGpu前发布context/window，并在UI主线程运行官方阻塞loop。
独立不加载XEX/资产/guest GPU，500ms后正常关闭、native HWND销毁、graphics清理，最终多次build/run均exit0。
实际窗口隐藏；公开SetPresenter是void，只记录binding_requested，未读取protected getter。
**surface_verified=false、visible_frame_verified=false**，不能把非空presenter或窗口创建当成首帧。
精确runtime/plugin DLL错误在创建输出/构建前拒绝，负例通过。

## 原标题接入与对照：Verified观察，不推断因果

同一原20成员根，headless新探针与三次presentation新宿主均执行真实xstart/main到20秒观察边界、exit26，未发生新fatal/exception。
原caller/LR等待链不变：82869BBC调用NtWaitForSingleObjectEx，LR82869BC0，CTR8248B100。
独立对照中presenter-null从headless514条降为presentation0条；初始化与UI loop enter/exit0均有实际记录。
这表明本次接入消除了null-presenter诊断，**不证明等待由/不由GPU造成，更不证明死锁或可玩性**。
标题仍按既有诊断方式有界进程终止，不宣称正常游戏关闭或完整runtime清理；正常清理仅在独立无XEX实验验证。

候选handleF80000AC在采样线程恢复后，以固定发行SDK公共API进行非阻塞TryAcquire/RAII引用观测：

```text
status=observed type=2 type_name=event guest=3007D018 host=0
primary=F80000AC aliases=1 name_hex=- event_type_known=1 event_type=1
event_signal_known=0 refcount_known=0 producer_known=0
```

两模式六条及后续重复均确认Event类别/无名/单alias；不同进程相同数值不等于同一个共享对象。
未读私有引用计数，不修改/补写事件、vtable或GNatives。TryAcquire忙时记录busy，不阻塞等待以探测状态。
**Query(state)会Wait(...,0)后restore、临时消费信号**，故只调用Query(type,nullptr)。
API报告kind1的枚举含义为auto-reset，但发行Initialize未见更新Query使用标志；实际backend reset kind未独立验证，
signal/refcount/producer全部unknown。父Python先核验实际发行DLL SHA再attest，进程不是自行重新hash；采样后lookup不是原子时刻快照。
详见[等待对象](RESEARCH_WAIT_OBJECT.md)、[presenter](RESEARCH_PRESENTER.md)、[复现命令](EXPERIMENT_PRESENTATION.md)。

## 测试、回退和失败保留

源码基线502→修改531→恢复502均OK；Windows基线/恢复skip1，修改skip2（额外mock C++编译器不在PATH）。
另在真实VS/Clang子进程环境执行等待观测8项全部通过；Linux/Windows CI与游戏验收分别记账。catalog通过。
隔离回退逐个恢复152基线文件hash并移除新增文件；主目录保持修改态。
恢复源码配旧phase10构建及同一原根，实际恢复headless/null-presenter/exit26，新窗口与Event元数据观测标记消失。
测试通过后提交/推送并核验远端HEAD、全新clone测试及4项CI；实际交付状态存本地delivery-verification。

保留失败：standalone两轮protected API编译错、引号/测试入口错误、mock期待hex错误；
标题第一次user32未链接的LNK2019/LNK1120及partial-map解析错误；全树相等断言对3个元数据差异的失败。
没有修改SDK、补空stub、吞fatal、手写原GNatives或强制唤醒事件。
`local/analysis/phase11/`保存所有命令/输入hash/逐字日志/退出码、基线与原独立证据、真实运行及回退；
`verification/`含MODIFIED_FILE.py、DIFF_FILE.patch、VERIFICATION.txt、可执行ROLLBACK.sh。完整原资产/生成源/对象/二进制/日志ignored。
下一项需追原Event创建/传递/唤醒链并独立验证真实swap/可见呈现；当前仍未验收首帧、输入、音频、地图/战斗、存档或换盘。
