# 最小实施计划

新增 release-source-lock.json、release-source.py、release-source.test.py。复用原bootstrap --archive及现有清理；修改deveco26-pr82-gates.yml、deveco26-gates/workflow.test.cjs、gates.py/gates.test.py，必要时仅新增本轮integration测试辅助文件。更新活动Spec到009，不修改旧006–008。

下载层与文件拼接分层：固定API/no-auto-redirect传输器可用自动mock测试实际request headers/redirect；小字节夹具表达所有失败路径。来源JSON与URL读取上限，分片按锁定大小流式读取；输出只保留阶段/状态/HTTPcode和固定身份，不输出响应Location/token/原异常文本。

先测试新来源缺证不能放行和workflow缺私有入口的真实RED，再最小下载/回拼GREEN，补实际函数失败回归。集成用已核原ZIP作为测试网络体，不产生永久分片副本；实际子进程验证token剥离和旧bootstrap调用契约。旧SDK/产品代码未变，不无谓重复HAR/consumer构建。若需实际bootstrap准备，以原包复用一次且遵循已锁工具和独立清理，不把模拟结果称远端验证。

来源结果必须绑定实际checkout/tree/trackedBytes及来源锁SHA/原锁SHA，finish检查与当前源码一致。来源失败、bootstrap失败、owned输入清理失败都传递失败。精确提交后只做必要clean重放，删除可重建clone/临时ZIP，证据保留。
