# UE3 资源勘测

## Verified：原版字节与目录
盘 1 含 1912 个 UE3 magic 候选，盘 2 含 2233 个。样本 MC2Game/CookedXenon/01_SentinelLab_zombie.xxx 的头前 8 字节为 `9e2a83c1 001901be`。
全部候选的包头数值分布已扫描：盘 1 的 1912 个和盘 2 的 2233 个均为大端 446/25。
工具对全部候选记录 package_version_candidate，但状态仍为 magic-only；字段解释不是完整反序列化。

## High-confidence deduction：版本交叉核对
按大端版本字的低/高 16 位得到 446/25。UEViewer 作者源码以该组合识别 Magna Carta 2。
固定版本来源：[UnPackage.cpp](https://github.com/gildor2/UEViewer/blob/a0bfb468d42be831b126632fd8a0ae6b3614f981/Unreal/UnrealPackage/UnPackage.cpp)、[GameDatabase.cpp](https://github.com/gildor2/UEViewer/blob/a0bfb468d42be831b126632fd8a0ae6b3614f981/Unreal/GameDatabase.cpp)。
这一匹配不证明精确引擎源码版本、对象解析、重建或 PC 加载成功。

## 本地化候选
两盘均观察到 MC2Game/Localization 下的 Coalesced.int（1495972 字节）、Coalesced.jpn（1393315 字节）、Coalesced.kor（3200 字节）。
文件存在与大小已验证；内容、编码、语言完整性及使用优先级未验证。尤其不能把小体积 .kor 直接当完整韩文库。
当前正式原文及译文条目均为 0，没有伪造游戏句子。

## 未知与下一实验
压缩块、name/import/export 表、UnrealScript、native 绑定、字体图集、纹理、音频及流式依赖均待解析。
先验证包表与 Coalesced 记录边界，再研究稳定 ID 和字体引用，最后进行有版本保护的副本回写。
[Epic cooker 文档](https://docs.unrealengine.com/udk/Three/ContentCooking.html)说明平台 cooking 会处理资源格式，不能盲目全包换序或假设通用 Windows UDK 可加载。
