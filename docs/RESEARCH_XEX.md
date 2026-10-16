# XEX 初步勘测

## Verified：固定头与指纹
两盘根目录 default.xex 均为 19611648 字节，镜像绝对偏移均为 3899768832。

|盘|SHA-256|
|---|---|
|1|26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f|
|2|44976b6bf9f978312f14387ea4e60bbdfffd1a8aa72f31841f7a58ab2ebef586|

两者均为 XEX2；大端固定字段：module_flags=1，PE 数据偏移=0x4000，security 信息偏移=0xA0，可选头数量=17。
只读取与散列原版区间，没有导出、修改或执行 XEX。同样固定头和大小不代表两盘代码一致。

## 尚未验证
Title ID、Media ID、版本、执行身份盘号、可选头、压缩/加密标志、导入表、加载地址、PPC 指令与函数边界均为 NOT TESTED。
未生成 C++，未编译原生程序，未执行游戏逻辑。下一步对两份 XEX 分别验证可选头边界与身份，再选择重编译器实验输入。

## 复现与来源
执行 RESEARCH_GAME_STRUCTURE 的扫描命令，过滤 JSON 中 type=xex2，查看 xex_header 与 sha256。
[Xenia XEX2 定义](https://github.com/xenia-project/xenia/blob/master/src/xenia/kernel/util/xex2_info.h)用于后续结构研究；本轮固定头功能不是完整 XEX 验证器。
