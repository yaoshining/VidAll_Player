# GitHub Actions 上下文作用域返修

## 实际阻塞

用户批准的2e73691345642723b88c224b67834f264f96d8af已非force快进推送；[run39995258720](https://github.com/yaoshining/VidAll_Player/actions/runs/39995258720)结论failure，jobs=0。GitHub页面原注释明确：normal-core.yml第21、89行job.env中的`runner.temp`为Unrecognized named-value。工作流未进入host/HAR阶段，因此本轮远端正常核心门禁没有通过，也不存在对应目标构建artifact。

本地25契约和47host、真实HAR通过属实，但未覆盖GitHub表达式的上下文可用性；不能用它们改写远端失败。原错误YAML可从2e736913精确提交恢复；实际注释与actionlint RED见[evidence](evidence/ci-scope-repair/github-annotation.json)。

## 最小修复及TDD

只在初始化step内计算`CI_OUT="$RUNNER_TEMP/..."`，写入GITHUB_ENV供后续step使用，不改变产品/目标输入/ci-target。actionlint1.7.12官方Darwin ARM64/Linux AMD64归档锁定SHA256；下载后先验摘要再仅提取单个普通actionlint文件，错误hash、缺文件、链接、重复名称拒绝。工具仅存在临时work目录，不提交/上传二进制。

全仓三份workflow由实际actionlint解析。既有deveco自托管标签显式声明，Actions schema/表达式规则不关闭；外部ShellCheck/Pyflakes不在本修复范围。先在原workflow得到与GitHub相同的scope RED，再修复为GREEN；新增job.env引用runner、job.if引用steps两个变异必须被实际解析器按预期上下文拒绝。原六种工作流变异保留。缺schema-result.json时host收尾不能绿色。

实现后25个契约、2个归档/平台测试、10项工作流结构检查、6种既有变异和2种真实scope变异通过。精确提交clean重放在冻结后写外部预览；本文件不提前宣称新SHA远端通过。

## 验收边界

不改产品、旧八库、旧candidate、原Player/TV、默认SDK/签名，不重复设备或长播。2e736913的真实本机unsigned HAR证据保留，本次未改target runner/源输入，不将其冒称新SHA目标构建。远端新head和PR merge仍须在精确批准后实际运行。formalArtifactAllowed=false；既有真实GPU/低API/物理HDR等未验项目保持原状态。
