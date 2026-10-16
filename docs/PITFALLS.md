# 调查陷阱与回归

1. Verified：本地起始只有通用模板，无 Git 元数据或测试；旧模板示例不是已实现功能。
2. Verified：同路径 default.xex 在双盘哈希不同；不能以大小相同推定可混用。
3. Verified：盘内无扩展名文件若直接对“镜像名::成员名”调用 suffix，会误认镜像后缀；已修复并加入回归测试。
4. 已避免：只看 .xxx 后缀就认定资源可解析；当前类型要求 magic，状态仍为 magic-only。
5. 已避免：把清单总字节数当磁盘占用；统计包含镜像与其成员，必须分开解读。
6. 未验证：UE3 Windows 可直接读取 CookedXenon、字体替换即支持中文、解锁帧率不影响逻辑，均不能作为工程前提。
7. Verified：GitHub CLI 未登录与 Git HTTPS 凭据是不同通道，发布状态须以实际 push/fetch 结果为准。

8. Verified：INT 后缀并不意味着实际内容为英语；本游戏 Coalesced.int 存在大量韩文文本。内容语言应按证据逐条确认。
9. Verified：大端长度字段下，Coalesced 宽文本和本游戏部分 UE3 FName 载荷是 UTF-16LE；盲目同端序解码会失败或乱码。
10. Verified：对既有 JSON 输出直接 write_text 会跟随硬/软链接并污染输入；本轮格式工具采用随机临时文件+原子替换，硬链接回归测试通过。
11. Verified：UE3 的 inventory、成员范围与哈希必须在 summary-only 分支也先校验；非空表不得覆盖 summary，避免接受恶形表。
12. Verified：路线 A 首轮严格分析在两条分支目标上失败；保留首轮日志，不能 force 或静默 stub 掩盖未解决调用。后续 hint 实验的结论单列。
