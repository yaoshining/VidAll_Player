# 规格：当前正常核心的 PR 与组合 CI 门禁

日期2026-10-24；基于 `ca3a8a5172b71da957b4dabe99e10250301fe290`，在隔离分支继续fast-forward，推送前新SHA需批准。仅改CI、验证工具、对应测试和本规格；产品源码、固定八库、旧证据/候选、原Player/TV与SDK不变。

## 用户故事

US1：审查PR #82时，CI实际测试GitHub生成的PR merge checkout，而不是拿旧head成功冒充组合成功。US2：同一组合既通过宿主真实函数/负例门禁，也用当前固定八库真正编译unsigned HAR及核对包内身份。US3：输入缺失、工具/构建失败、身份不匹配或fork不能执行受控runner时，结论明确失败/未满足，且保留可公开的失败证据。

## 要求

- FR01：normal-core监听main目标PR、main/原normal-core/当前docs分支push、workflow_dispatch以及merge_group checks_requested；无路径过滤导致相关PR被静默跳过。默认checkout为事件SHA，记录event/ref/checkout/base/head/parents。PR须验证两父merge组合；merge_group核验其head/base；push/manual核验checkout等于事件SHA。
- FR02：每次运行仍执行现有完整47条host checks及新增门禁回归，不修改固定库锁或放宽原失败规则。
- FR03：新增self-hosted macos/deveco unsigned HAR job。仅执行当前源码的Player bridge/ArkTS目标编译并消费固定八库；先核对来源/实际输入，clean后真实devecocli模块构建，最后验证HAR包含正常ARM64九库，八核心hash逐一一致、bridge为真实ARM64 ELF及当前构建输出。不能运行旧source-lock的producer重建job替代它。
- FR04：先记录干净源码与固定输入字节；实际 devecocli build clean 仅清隔离工程生成物，同时记录官方 ToolProvider 选择，再通过 DEVECO_CLI_STUDIO_PATH 绑定相同 Studio；clean 先于SDK身份核验，不能声称已先验证工具链；核对 API24、metadata 和 clang/nm/readelf 精确 hash，目标 compile_commands 必须使用同一 clang/sysroot。不新增必填但未配置变量，不硬编码开发机路径，不下载/改默认 SDK。探测缺失/歧义、SDK漂移、缺工具/输入/输出或非零/timeout均失败，不伪造skipped-success。
- FR05：目标runner不探测/复制签名，不执行设备或HAP；fork PR不进入受控self-hosted runner，最终组合门禁必须明确未满足。GitHub托管host job可执行fork内容。最终判定同时要求host与target成功，不能把target skipped归为通过。
- FR06：从准备阶段建立证据目录，捕获命令退出/timeout/失败文本，固定身份字段及输入/目标产物hash。always收尾按白名单脱敏并验证公开文本；拒绝上传库/HAR/HAP/SDK/凭据/签名或原始设备日志，公共门禁不通过不上传。依赖安装失败也能记录步骤结果，不能空artifact成功。
- FR07：在新规格内保留RED→GREEN/负例、精确clean重放与未验收范围；新SHA批准前不push。API/设备/物理HDR/正式发布仍不在此关闭，formalArtifactAllowed=false。

## 成功标准

SC01：冻结旧workflow/缺少CI runner时测试明确RED；GREEN拒绝错eventSHA/PR父关系、缺输入、错包、build失败/timeout以及target被skip。SC02：实际host入口与一次真实unsigned HAR目标构建通过，未生成新producer库。SC03：精确提交在clean checkout重放并记录source/tree/event身份，远端结果仅在批准后取得；旧66e9d3 CI不借用到新SHA。

## FR08：工作流解析作用域返修

2026-10-24实际run39995258720在job启动前失败，GitHub明确拒绝job级env使用runner.temp。新增固定官方actionlint1.7.12检查全部工作流的schema与表达式作用域；自托管标签仅显式声明真实deveco，不忽略表达式规则。CI_OUT改在step运行时通过RUNNER_TEMP/GITHUB_ENV初始化。归档必须摘要匹配，两个非法作用域负例须由真实解析器拒绝；缺schema结果也禁止host绿色。原失败与本机HAR记录保留，远端新SHA仍需精确批准。

- FR09：文档 catalog 不得作为 ToolProvider 证据。只执行一次 clean，其日志无唯一实际选择、退出错误或后续 SDK 精确身份不符均禁止 build。输入缺失/漂移在 clean 之前拒绝，保留旧输出清空检查。新远端 SDK 身份与新提交 CI 均须实测。
