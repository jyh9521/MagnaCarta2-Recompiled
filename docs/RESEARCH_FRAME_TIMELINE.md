# 调用时间轴与guest-output读回契约

结论和原始数值见[阶段25](PHASE25_RESULTS.md)。

## 可重复运行接口
```powershell
python -m tools.research.probe_title_entry --help
python -m unittest discover -s tests -v
```
在固定原XEX、SDK/runtime/GPU hash、strict生成树和197对象输入下，`--trace-frame-timeline`开启五原函数RAW观察，`--capture-guest-output`在有限窗口末尾读回一次现有SDK guest-output。二者独立，捕获要求真实GPU/presenter。真实窗口同时保留原counter/schedule与精确panic/早期AV观察。

## 时间轴合同
pre/post保留原r3..r10、context、host线程、LR/SP、native tick、唯一call/seq、TLS parent/depth；post result是原body返回raw r3。TLS嵌套不等于完整guest调用图；函数LR/原CFG需独立绑定。wrapper保留完整PPCContext、errno/LastError和原异常，原委派恰一次；mock只证明包装透明，不代替标题验收。
每target8192槽防止一条热点饿死其它target。unwound是原委派异常退出计数，inflight只表示宿主观察区间，pending/pre未配对不是死锁。freeze不停止原body；容量、冻结边界和父记录缺失显式保留。native tick区间包含观测/调度，不将嵌套区间相加作性能统计。

## 捕获合同
SDK RawImage为R8G8B8X8，stride可含padding，最后一行无需padding。PPM只写RGB；全黑合法图片也可captured，但0非黑像素不伪报可见内容。readback成功、PPM写入成功、独立像素/hash校验、实际内容查看以及可见present是不同证据层。
SDK readback可能等待GPU fence；不加主动Refresh、不造帧、不延长诊断timeout冒充修复。单进程超时保留原失败和readback前timeline，窗口仍隐藏，readback不证明可见present/交互。
