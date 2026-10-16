# 构建与复现

## 当前可执行成果
本轮仅构建/测试研究工具，不生成游戏程序。Python 3.12+，Git；标准库，无 pip 安装步骤。
在项目根目录执行 `python -m unittest discover -s tests -v`。
Linux/Windows 均采用相同 Python CLI；本轮实测环境为 Windows、Python 3.14.2。

## 数据输入
自备 Xbox 360 光盘镜像或提取目录。支持的 XDVDFS 分区候选偏移见 `docs/FILE_FORMATS.md`。
所有扫描命令显式传入输入，绝不自动寻找磁盘上其他游戏。
```powershell
python tools/inventory/scan.py local/disc1.iso --disc disc1 --xdvdfs --output local/analysis/disc1.json
python tools/inventory/scan.py local/disc2.iso --disc disc2 --xdvdfs --output local/analysis/disc2.json
python tools/inventory/compare.py local/analysis/disc1.json local/analysis/disc2.json --output local/analysis/disc-comparison.json
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
```
`local/disc1.iso` 为文档路径约定，不是要求将已有镜像再复制一份。实际输入可为任意显式路径。
完整扫描会读取整张镜像并再次读取各文件区间，因此 I/O 总量大于镜像大小。

## 结果与退出码
扫描 JSON：schema_version=1，files、errors、summary。0=完整完成；1=有输入/解析错误；2=参数或输出失败。
errors 非空的清单不允许作为双盘比较输入。总字节数是记录字节和，包含镜像和成员，不能当作磁盘占用。
工具只读输入；输出原子替换。输出不得位于任何输入目录内或等于输入文件。
固定头识别不代表完整资源解析。空目录扫描成功也不代表已提供游戏数据。

## 版本确认和发布
第一轮原版指纹见勘测文档。尚无支持版本白名单或二进制补丁器；不得应用盲偏移。
原生编译目标、C++ 编译器配置及运行时依赖尚待路线实验决定。
发布检查见 `docs/BUILD_AND_RELEASE.md`。回退本轮源码在隔离副本验证，原镜像未写入。
