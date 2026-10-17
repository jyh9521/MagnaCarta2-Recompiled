# 82E078C0：完整byte flag叶与副作用

## Verified / High-confidence deduction：原范围
固定XEX SHA26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f、原loader与展开像d18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9重新核验。原82E078C0起12bytes为896321ac556307fe4e800020，SHA647f0e9b625de7198c3695d9dc3bda6707c347a543408d0d1f510d4baed5fa1c。
全44484条PDATA无覆盖；前16bytes81630000814b014c7d4903a64e800420末bctr，后16bytes000000008063221c4e8000203d608325为padding/不同word叶。原只读指针词、独立caller与前后边界支持高置信保守完整12-byte范围，不把无PDATA本身当大小证明。两项旧生成metadata缺entry。

## Verified：读取与r3/r11完整64-bit副作用
LBZ先用旧r3.low32计算EA=(oldr3.low32+21AC)mod2^32，读取一个byte并将其零扩展写完整r11.u64。RLWINM的SH0/MB31/ME31/Rc0只保留该byte的bit0，写完整r3.u64=0/1；它不是64-bit环绕mask，且不改CR。BLR保留LR/CTR，各其它GPR、CR/XER、FPR/FPSCR、vector和内存不变。
byte读取没有4-byte对齐要求。EA的guest wrap与Windows在E0000000以上额外1000的physical bias是两层，必须独立验证；r3和r11原上32bits都不可残留。R4未使用，类/字段名未知。

## Verified：原样生成体3072例完整正常返回
先独立原code/byte-memory oracle，再strict生成。实际body原样提取，不替换宏/原callee，不手写body或原表。
全部256byte载荷×12地址=3072例；含随机upper-r3/r11、奇数EA、wrap至0/1、DFFFFFFF/E0000000阈值、FFFFFFFF及最后额外host页。独立写byte，不通过配套store宏避免同错抵消。
实际SDK PPCContext/宏、Clang /Od /fp:strict编译运行exit0，逐case完整context比较只允许r3/r11改，八页全部字节和host MXCSR不变，完整返回并释放页；末行BYTE_FLAG_MEMORY pages=8 cases=3072 released=1 failures=0。context/FPSCR/编译器身份及整SDK宏保持固定。
只证明有效映射普通内存，不覆盖fault/MMIO/PPC全部硬件状态，不证明guest0在标题有效或标题中本叶实际返回值。边界wrap不等于允许扫描任意进程内存。

## 失败保留
原验证首次邻居after元数据起点沿用+8而不是+12，测试实际RED后纠正为+12；原目标/邻居bytes/hash判断始终正确，首份proof保留，final proof重新验证。whole-range PDATA重叠守卫不只检查入口点。
实际生成体首次fail-closed提取因预期rotate模板不符而exit1；SDK正确输出clrlwi别名优化r3=r11.u32&1。只修严格模板与合成fixture，不改SDK或生成body，再跑3072通过。坏XEX实际exit1/无输出JSON记录保留。
新profile最初RED未知入口/缺strict要求；加入完整继承hint链与strict守卫后GREEN，未知tree和非strict对象仍拒绝。
