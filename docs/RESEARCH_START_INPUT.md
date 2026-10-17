# START自动输入及原消费观察契约

结果与边界见[阶段26](PHASE26_RESULTS.md)。

```powershell
python -m tools.research.probe_title_entry --help
python -m unittest discover -s tests -v
```
--trace-input默认关闭，要求固定原XEX/SDK/生成树/197strict对象及456字原范围守卫、原adapter/consumer dispatcher和strong原body分址绑定。--scripted-start自动开启输入观察，在官方default InputSystem上AddDriver；--scripted-controller-neutral保留同设备/caps但不按任何键。二者不是直接修改游戏变量或修复runtime输入实现。

原GetState成功后只读16B普通RAM，错误输出不读；原r3(user)/r4(stateptr)/LR/SP完整保存，返回raw status与BE packet/buttons分别解释。原helper仅key.low32=5且LR827B4D10/user.full64<=3记录，其他调用原样委托无guest读取；用户越界单独统计。不追写原事件vtable。

slot覆盖、weak元数据、drop lag、pending/冻结后suppressed与异常unwound不自动等价死锁；capture_verified表示该捕获合同，不是物理输入/原UIcallback或玩法证明。state输出不能依driver自身phase声称成功，必须核验原adapter真实返回及原helper存储变化，再绑定原SDK图像内容。

同设备neutral/pulse对照固定EXE/SDK/资源根，单独恢复原源码host并重新全量链接运行。Synthetic API与所有图片保留在诊断/ignored空间，默认普通启动仍原default driver。START脉冲是有限自动测试，今后其他输入需先核验原位/消费条件，再扩展明确脚本，不通过跳fatal或直接UI调用推进。
