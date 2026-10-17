# 计数生命周期观察契约

阶段24的完整发现与边界见[阶段24结果](PHASE24_RESULTS.md)。

## 原语义
82399650原子增counter；83263ACC为0时内部减回，否则保留原8-byte队列对象。822D0A68产生{manager,payload,alignedsize}描述符，非空时写原table82153638和counter地址，再发布write游标并清reservation标志。consumer82399090在823990F8调用原slot+4，再调用slot0并推进read。实际82399738读取object+4执行原子减并返回8。
manager83276B18的+0/+4为begin/end，+8 write，+C wrap，+10 reservation，+14 read，+18 alignment；这些是分开读取的原字段，不是锁定快照。原counter83265218不是vtable输入夹具。

## RAW而非替换游戏实现
SDK `REX_HOOK_RAW`配合实际生成PCH的weak sub alias，使host strong sub覆盖直接调用、dispatcher映射和RegisterFunctions；wrapper仅观测并调用强`__imp__sub`原body。独立COFF/PE与真实dispatch绑定证据保留。仅SetFunction会遗漏直接调用，不能作为完整seam。off只委托原body；原源码实际回退则移除新wrapper并重编host。

## 只读输入与解析
counter_observation只读固定counter/global及已匹配nested reservation描述符；callback追踪保存的原r3而非返回值8。所有guest地址限定普通RAM或原image，预flight后ReadProcessMemory，guard/noaccess/MMIO不追踪。不查询或消费等待/锁状态。
queue_watch的head是直接BE32[manager+14]，不是head+20。只在范围有效时最多读32字节，table只允许原image内12字节；读表不执行表中函数。解析器对帧、slot、字段、drop/pending、prefix长度与原字值进行验证，并保持executed_callback_proof=False。

```powershell
python -m tools.research.probe_title_entry --help
python -m unittest discover -s tests -v
```
真实诊断同时使用`--trace-counter --trace-schedule`与独立panic/CS捕获。execute API可保留无panic的有界观察结果；CLI请求panic的既有成功门槛不被放宽。
