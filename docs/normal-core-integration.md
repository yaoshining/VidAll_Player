## 独立正常核心接入分支的迁移约束

本分支保留原有播放 API 签名，但新增进程初始化前置条件。所有 Player 创建之前必须从根入口初始化；仅显式接受受控退出策略的宿主可使用该组合：

```typescript
import { initializePlayerRuntime, onPlayerTerminal, createPlayer } from '@vidall/player';

await initializePlayerRuntime(context, {
  terminalPolicy: 'controlled-app-exit',
  deadlineMs: 3000
});
const unsubscribe = onPlayerTerminal((info) => {
  // 立即提示故障并禁止重建播放器；只读缓存诊断。
  // 不再调用普通 release/join/mpv。宿主应受控结束整个应用，用户再打开。
  context.getApplicationContext().killAllProcesses(true);
});
const player = createPlayer();
```

deadlineMs 为必需整数，范围 1000–10000ms。native 首次终局锁存后独立计时，宿主回调或 UI 未响应也不会延后；截止到达执行进程退出。该行为必须由宿主明确选择，不会默认启用。初始化同配置幂等，不同配置拒绝；失败状态锁存，不能继续创建播放器。

正常路径仍按原契约等待准备事件后播放，并在结束时 release。终局后所有实例拒绝新播放/命令，已有诊断快照标为 cached-terminal；无快照时返回错误，不能把旧值冒充新采样。示例的故障提示、应用保屏释放与退出编排见 `fixtures/normal-core-consumer`。

**TV 本轮未接入。** 后续 TV 需增加上述启动与终局接管，同时原子移除旧六库并换成包含九库的新 HAR，禁止混装；旧候选仍保留。Player target22/compatible15、TV target22/compatible19 未改。平台符号声明审计不等于低版本真机验收；当前正常组合只在 API24 目标验证。原仓 entry 示例本轮未迁移到必需初始化，不能用其构建代替新 SDK 消费证明。独立消费者才是本轮实际根入口验证工程。

该分支仍为候选接入验证，formalArtifactAllowed=false；无正式发布或 TV 替换授权。
