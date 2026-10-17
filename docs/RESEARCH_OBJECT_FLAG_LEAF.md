# 对象最高位读取叶验证合同

见[阶段28](PHASE28_RESULTS.md)。

```powershell
python -m tools.research.verify_object_flag_leaf --help
python -m tools.research.probe_callback_codegen --help
python -m unittest discover -s tests -v
```

新entry-profile `object-flag-leaf`追加单一8233D3D8/size0xC hint，继承全部旧hint并验证原版本/字节；未知输入拒绝，不静默回退。运行验证器时必须显式提供原XEX及loader-source；需要实际生成体差分时同时提供generated/sdk/compiler/vcvars，缺一即拒绝；optimization可Od或O2。输出必须新路径，不覆盖输入。生成体必须唯一、完整三条原指令注释及唯一init/register映射、精确PCH地址宏，禁止替换宏伪造成功。

工具的execute是32位EA/BE32/r3-r11寄存器副作用oracle，不是游戏native兼容实现；harness只抽取实际生成body且保留完整ctx及映射页。返回0/1是字段最高位，未命名为未经证实的业务属性。8页/1536case/释放/完整逐行字段/零退出全部具备才承认完成，进程崩溃不能沿已有成功行宣称PASS。

新titleprofile绑定测得strict tree，capture/FP都必须显式认可；每TU均须exact /fp:strict，fast或mixed拒绝。历史profile继续使用原树做实际回退；仅恢复源码而保留新生成映射不能重现旧缺登记fatal。真实入口继续使用24成员根、原SDK及有限START/A；新黑场和缺电影资源的因果需要后续独立实验，不修改原状态推进。
