# 第一轮验收记录

日期：2026-10-16（Asia/Tokyo）。环境：Windows、PowerShell、Python 3.14.2、Git 2.45.1.windows.1。

## 实际交付
- 保留既有 LICENSE、翻译许可、本地约束与占位目录，原始模板逐文件备份并散列后填写项目文档。
- 初始化 Git，连接用户指定远端；提交与推送结果另以实际 Git 记录为准。
- 只读递归清单、流式 SHA-256、XDVDFS 成员遍历、固定头识别、双盘比较、本地化基础校验与 CI 配置。
- 四份原版勘测、两份双路线调查、基础工程文档、术语与审核流程。

## 验证
|项目|实际结果|状态|
|---|---|---|
|修改前 unittest discover|Ran 0 tests；NO TESTS RAN；exit=5|NOT TESTED（没有测试）|
|修改后 unittest discover|43 tests；OK；exit=0|PASS|
|本地化空目录结构校验|PASS catalog；exit=0；正式译文 0 条|PASS（仅结构）|
|双盘扫描|2017 / 2341 条记录（均含镜像自身），errors=0，exit=0|PASS|
|全量 UE3 候选头|盘 1 全部 1912、盘 2 全部 2233 为大端版本候选 446/25|PASS（仅头字段）|
|双盘比较|1631 同内容、3 异内容、382/706 独有；exit=0|PASS|
|原生代码生成、C++ 编译、逻辑执行、图形、可玩性|均未执行|NOT TESTED|
|GitHub Actions 各平台矩阵|提交 ffc5559 的工作流已完成，conclusion=success|PASS|
|隔离副本回退|restored=9，removed=30，原始哈希恢复；0 tests / exit=5|PASS（恢复模板状态）|
|远端干净克隆|43 tests OK；空 catalog 结构校验通过|PASS|

## 命令与证据
```powershell
python -m unittest discover -s tests -v
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
```
完整扫描命令见 RESEARCH_GAME_STRUCTURE，双盘指纹与差异见 RESEARCH_DISC_LAYOUT。
本地日志、修改副本、差异、原模板哈希及隔离回退证据保存于 local/analysis/phase1/。
回退前核对修改态哈希，恢复原模板并移除本轮新增文件；回退副本应恢复“没有测试”的原始状态，而不是伪造原版游戏运行结果。

## 第一轮之后
当前没有原生运行程序、完整资源解析或正式中文文本。下一轮优先 XEX 可选头/身份、Coalesced 最小记录与包引用图，详见 NEXT_STEPS。

## Git 与云端证据
首个工程提交 `ffc55593be69d096965789be870877c32dcc73f8` 已推送 main，远端 SHA 与本地一致。
[GitHub Actions 运行记录](https://github.com/jyh9521/MagnaCarta2-Recompiled/actions/runs/38904741377)：Windows/Ubuntu、Python 3.12/3.14 四项组合全部成功。
该云端结果只验证工具，不代表本游戏编译、启动或中文显示。
