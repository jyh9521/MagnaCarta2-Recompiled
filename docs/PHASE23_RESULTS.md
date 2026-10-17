# 阶段23：原延时路径与计数轮询

## Verified
原82869800完整0x90、所有直接分支引用、整数参数/alertable条件独立核验。默认关闭透明host-IAT调度observer及只读caller-frame取样已实现；197个既有strict对象重新核验后重编host并全量链接58417映射，未修改游戏生成体/SDK/资源。
真实24根最终窗口55个晚期样本确认main parentLR82E2080C，原counter83265218=2、threshold=1、interval=0/alertable=0。原SDK delay持续返回；45秒仍运行的直接原因是原main计数轮询条件未满足，不是一次延时API卡45秒。静态潜在减计数回调82399738已定位，但其实际dispatch/上游为何未降低counter仍未知。
[完整原语义、证据与限制](RESEARCH_SCHEDULE_POLLING.md)。正常CS反复有返回，CS槽overflow明确记录，不宣称完整覆盖/死锁。早期坏CS AV未重现/未修复；有效oldLR调用与旧坏地址分开。

## 测试、回退与交付
保留解析器实际RED和observer原生mock记录；根测试、catalog、源码基线/修改/隔离回退及全部原hash验证通过。最终同EXE on/off/on/off有两次实际flag/IAT回退，恢复源码后另实际重编host/全链接并运行24根；原失败与exit26均保留。主工作树保持修改态，原资源/生成体/二进制不入库。
完成后提交推送，远端HEAD、新clone及四项CI另核验，精确命令/输入/字面输出/exit和四件套保存在ignored local/analysis/phase23/verification。尚无首帧或可玩性验收。
