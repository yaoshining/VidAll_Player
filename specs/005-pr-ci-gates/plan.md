# 计划：真实执行与固定输入绑定

## 现状及取舍

normal-core目前只有原集成分支push/manual；其47项宿主门禁有效，但没有事件/merge身份记录。test-player现有HAR/Hypium职责保留，签名探测不引入新门禁。build-libmpv被skip的旧源码构建依赖旧native/config/sources.lock，不能用它重建或证明当前release/inputs/004-normal-core固定输入。本轮新增专门normal-core unsigned HAR目标门禁，不改变上述旧workflow。

使用deveco-cli skill的 `devecocli build clean`、`devecocli build --modules vidall_player@default`。目标工具链由 `DEVECO_CLI_DEBUG=1 devecocli docs catalog` 只读探测官方实际 Studio 选择，再以 `DEVECO_CLI_STUDIO_PATH` 固定同一目录用于 clean/build。精确锁定 API24 / 6.1.1.115 metadata 和 clang/nm/readelf 字节；与既有004目标输入使用的本机 DevEco 6.1.1.268 配套，版本号本身不替代 hash。拒绝探测错误/歧义和工具漂移，编译命令还须绑定同一 clang/sysroot。远端工具不同将明确失败；不新增未配置必填变量、不使用本机路径默认、不调整运行器配置。原始目标输出仅本地/runner保留，上传仅身份与脱敏日志。

## 最小实现边界

1. 新 `scripts/test/normal-core/ci-context.py`：实际git HEAD/parents与event JSON校验；只保存必要SHA/ref/repo字段，不保存完整用户输入事件。PR验证默认merge父提交，merge_group验证其head/base，push/manual验证event SHA。
2. 新 `scripts/test/normal-core/ci-target.py`：命令执行/超时/产物核验；使用既有normal-core-verify入口，不替换固定八库；输出私有work与公开public。缺输入必须在build前拒绝；HAR身份不符必须在build后拒绝。真实target运行禁止测试替身，测试通过临时PATH可控子进程模拟失败分支而不冒称目标通过。
3. 新 `scripts/test/normal-core/ci-evidence.py`：bootstrap/always收尾、步骤结果及上传白名单，关联CI上下文；复用check-public严格边界。工具安装失败/脚本非零与timeout都有结构化失败，不只留下空stdout。
4. 修改normal-core.yml：host与target两个必需结果；target仅同仓PR/受信任push/manual/merge_group执行。最终Ubuntu聚合job使用always检查两job结果，skipped/cancelled/failure一律不通过；fork不得因target跳过而全绿。测试当前source组合，不自动merge。
5. 新门禁测试表达实际helper/runner进程行为，并检查workflow事件/默认checkout/always失败上传/聚合条件；保留旧workflow基线RED。文档说明47 checks之外新增CI契约，不虚增原测试数量。

## 测试矩阵

| 分组 | 正常 | 失败/边界 |
| --- | --- | --- |
| 事件身份 | push/manual、真实临时git两父PR merge、merge_group | checkout错SHA、PR父不符、base/head缺失、单父冒充merge、非法event |
| 工作流 | PR/main/push/manual/merge_group触发，默认merge checkout，host+target汇总 | 去PR/merge事件、改checkout为head、删实际runner、删always上传、skip视success的变异拒绝 |
| 目标runner | 当前锁输入预检、clean/build执行、HAR九库匹配 | 缺库/错hash、缺SDK/工具、clean/build非零、timeout、exit0无输出、错库/缺bridge/旧输出 |
| 失败证据 | 成功/失败/timeout均有脱敏结果 | 路径泄漏、非文本/符号链接/超限、缺记录不能上传成功 |
| 真实运行 | 现有47host checks + 当前固定八库的unsigned HAR编译 | 不能把模拟devecocli/平台替身记为目标成功；不操作设备 |

## Spec Kit 与宪章

中文、TDD、真实构建与能力边界保持。复用speckit-analyze只读交叉核验；仓库旧prerequisite脚本不支持--require-spec，按支持参数运行后单独验证spec存在。新feature指针只在隔离clone指向005，不改旧004规格/证据。历史受控退出例外不扩展为新的产品行为。
