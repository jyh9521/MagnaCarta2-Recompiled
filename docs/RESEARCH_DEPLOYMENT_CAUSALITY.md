# WoodSword部署干预与独立早期AV调查

## Verified：唯一资源差异与原版身份
原Disc1整ISO重新流式hash为23e96219aa8b2116239c35e6f65013329bfd298d46a726edffa5224498028ac5，使用固定inventory及stage_runtime_files原工具，在新独立game-root-22重新提取原21成员加WoodSword。原21根/旧staging/原ISO不改，不用hardlink或替代资源。
新增 `MC2Game/CookedXenon/wp_Juto_st1_0_WoodSword.xxx`，offset4015128576，size196608，SHA256 f3ffd312d751b85a5d2cd954ff42a51bc1c012dfb5f272db09a5adb92177f85e；重新打开输出hash一致，原头9E2A83C1/BE446/25已独立验证。除根staging元数据外，只有该一个新增文件，21个共同资源全hash相同，无删除或修改。

## Verified：同一EXE的A/B/A/B/A
本阶段重新编译原样host、197对象显式全量链接；复用已验证的阶段17严格生成树与197个/fp:strict对象，重新hash验证，不声称重复编译未变TU。58170原函数/58416映射、全部对象链接、AMD64 PE、四host header、299 indexed-native最终效果验证通过。SDK1193文件/历史14组2758对象及原生成输入不变。
五次按顺序执行真实入口：21根基线、22根修改1、21根回退1、22根修改2、21根回退2。后四次复制完全相同EXE和GPU到独立日志目录；EXE SHA e771fba5ef1011989c7b94a696b3b1939df3209b482d551514603c44093bf893，SDK/GPU固定；显式环境变量仅MC2_GAME_ROOT改变。ASLR/线程时序/日志目录不同，不宣称全部运行状态相同。
21根三次均捕获原WoodSword BinaryFormat message、savedLR824844F4、零header及82390A70写guest3，原C0000005/3221225477终止。
22根两次均不再产生该panic/缺包失败，推进到原未登记目标82E078C0，C0000409/3221226505；实际CTR82E078C0、LR82D60BE8，r3分别41C0A000/41D8A000。两次真实失败均完整保留，不吞异常或越过fatal。
把资源根切回完整未改21根后，两次都恢复同原panic；新22根保留修改态。每次运行前后两root、EXE、GPU及源码/对象输入hash核验不变。

## 因果结论与边界
在本组受控重复干预中，补部署一个已验证原成员消除了指定panic，并可逆推进到相同下一fatal，支持缺部署是该panic的因果贡献因素，不再只是日志先后关联。
这不证明所有加载/解压步骤已逐项跟踪，不提供零buffer唯一写入历史，也不宣称这个部署问题解释所有启动故障。资源inventory、caller身份声明和离线分类都不是某条guest load实际读取了整个文件的证据。
新增deployment_evidence只读工具严格核验成员增量，精确filename匹配（仅允许一个已知../前缀）；无caller身份担保、未知AV、timeout、守卫失败、混合未明样本不产出有限关联结论。真实RED暴露Windows设备名路径未拒绝，补齐guard后13tests通过；无guard放宽。

## Verified：阶段18更早AV的精确位置
该次早期fault并非82390A70常量store，也不是未登记入口。固定rexruntime.dll导出RtlEnterCriticalSection_entry起点RVA408F80，fault RVA408F95原bytes8B4118为mov eax,[rcx+18]。实际read guest0043004E与PPC r3=00430036+18严格吻合。
原sub823BF278 PDATA范围0x80，823BF288读取BE32[入口r3+8]，823BF294加4得到CS参数，823BF29C转入r3，823BF2B4调用82E8DDEC/RtlEnterCriticalSection，LR823BF2B8吻合。实际EXE调用/import stub/IAT/SDK导出与原call一致，不只是nearest symbol猜测。
上游原824911F8虚调用slot8，入口对象来自outer r26；缺少该次入口对象/字段/生存期/并发写入捕获。由实际CS反推的00430032类似UTF16BE C2仅未证字节指纹，不能据此认定filename误当对象或原包导致AV。
当前五次试验未重现该早期AV；未修改SDK/critical section、对象内存或调度，也未修复其上游成因。下一步若重现，应限定捕获保存原入口对象r29及r11/r30/对象前缀，再建立坏指针来源，不制造CS或吞掉fault。

## 复现与证据
原成员提取可用 `python -m tools.research.stage_runtime_files --help`；依据21根staging选择相同成员并仅追加上述WoodSword，输出必须为全新目录。
只读部署增量CLI：
```powershell
python -m tools.research.deployment_evidence --baseline-root ROOT21 --modified-root ROOT22 --member MC2Game/CookedXenon/wp_Juto_st1_0_WoodSword.xxx --sha256 f3ffd312d751b85a5d2cd954ff42a51bc1c012dfb5f272db09a5adb92177f85e
```
ROOT21/ROOT22是用户自供原文件的新本地根，不是仓库资产。完整固定输入、原执行命令/字面stdout/native exit、原字节和PE证据在ignored local/analysis/phase19/，公共仓库只提交工具/测试/研究文档。

## 下一真实target的原码边界（Verified / High-confidence deduction）
固定原像82E078C0起12bytes为896321ac556307fe4e800020，SHA256 647f0e9b625de7198c3695d9dc3bda6707c347a543408d0d1f510d4baed5fa1c。全部44484项PDATA无包含；前bctr、末blr、后padding/不同lwz叶及一处原只读指针ref支持高置信保守完整叶边界，不把无PDATA本身当大小证明。
静态语义：从guest(r3.low32+21AC mod2^32)读取byte并零扩展写r11，将byte bit0写入完整r3.u64，原blr返回。原R4未被此叶使用，字段名/类型未知；实际原body尚未执行，不能把静态解码当差分验收。
两次实际fatal的LR82D60BE8/CTR82E078C0与原82D60BE4 bctrl、实际EXE间接call和ctxLR写入一致。原caller从83263C68取对象，再经[r3]表slot14C；未捕获当次global/table原值或实际vtable身份。两项生成登记metadata均无该入口，下一阶段应先独立完整语义实验再strict恢复。
独立审计首次假定trial目录有host.map发生FileNotFound；保留失败后，先验证EXE全hash与原链接产物相同才使用原map，不混用另一构建符号。
