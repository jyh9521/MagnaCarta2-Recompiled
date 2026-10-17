# A确认最小实验契约

参见[阶段27结果](PHASE27_RESULTS.md)与[START基础契约](RESEARCH_START_INPUT.md)。

```powershell
python -m tools.research.probe_title_entry --help
python -m unittest discover -s tests -v
```

沿用BUILDING中的固定原XEX、24成员资源根、SDK、严格生成树和197strict对象，显式添加`--scripted-start --scripted-confirm --trace-input`提供START后单次A；添加`--scripted-confirm-neutral`保持同设备/caps及START但不提供A。原`--scripted-controller-neutral`则抑制所有键，两种控制不能混称。confirm依赖START，confirm-neutral依赖confirm；默认均关闭。不是给用户手动游玩的输入适配。

A观察器过滤原helper key.low32=10、LR827B4DEC、user.full64<=3，仅只读obj.low32+4C0+C0*user，普通RAM地址及加法溢出失败封闭。与START共用同一RAW hook，原helper只委派一次。原456字/SDK/实际dispatcher强hook及原body分址守卫均保留。日志CONFIRM_EVENT与START_EVENT分开；oldword变化不冒充原虚拟callback的直接trace。

SCRIPTED_CONTROLLER旧行格式和原四场景输出保持；仅confirm模式追加SCRIPTED_CONFIRM，含confirm_neutral、32秒/500ms、A状态/释放与keystroke计数。parser要求显式请求/模式/守卫一致、BE按钮、地址/字段/配对身份及文件来源，不把driver自身计数当成功输入。旧宿主源码依赖通过实际include能力识别，不要求历史源码存在新的confirm header。

原失败中freeze/只读trace在fatal handler先写出，未读回GPU输出仍是未捕获图像；恢复对照的原SDK图像另外验证。native C0000409是保留的原fatal，不是正常guest关闭；测试预期它不表示已修复。严禁吞掉该fatal、空stub、手写原表或直接跳转NewGame UI来得到成功结果。
