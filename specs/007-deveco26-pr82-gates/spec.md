# 007：DevEco26 PR组合门禁与真实HAR消费者

基线6741c4a，独立分支codex/deveco26-pr82-gates；旧006/005证据、SDK锁、normal-core.yml语义、产品API/model/signing和固定八库不变。TV、候选、默认SDK不写入，不签名、不真机或长播，formalArtifactAllowed=false。

## 验收

- G01：新工作流绑定PR实际merge SHA及base/head父关系；push和merge_group绑定实际事件。错误SHA/旧树/漂移拒绝。
- G02：只有非fork且DEVECO26_APPROVED_EVENT_SHA等于实际事件SHA，才进入受审批环境deveco26-build；下载Secret仅该环境提供。缺值、skip、cancel、失败不能汇总为绿。环境保护必须远端回读，名字存在本身不是保护证据。
- G03：宿主、新target和consumer真实成功，源码身份一致，目标和consumer收尾成功，always汇总才通过。旧normal-core-result与旧API24锁不变，不做OR替代。
- G04：在同一可信job通过显式vidall_player@deveco26构建，唯一HAR的SHA与当次target证据一致；独立工程只能从该HAR导入@vidall/player，不能改成源码路径、旧候选、已存在缓存或其他target。
- G05：consumer真实构建unsigned HAP；解析实际OHPM依赖/编译输入，HAP恰有八固定库与当前bridge，逐字节对应当次HAR，API22/min15保持。构建通过不代表运行/真机验收。
- G06：consumer使用独立Hvigor home，清理只作用于该project注册的daemon，核对日志PID并有界等待；不停止其他项目。成功与失败都保留公开文本，不上传HAR/HAP/SDK/签名/凭据。
- G07：云端继续官方精确来源allowlist+归档hash，长期来源未确认时保持待验；本地可显式使用已核archive，不冒称网络验证。远端push/Secret/environment/ruleset/PR变更均先精确预览。
