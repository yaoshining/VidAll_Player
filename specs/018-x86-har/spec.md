# Spec018：x86_64完整播放HAR

状态：依赖受阻，未实现/未交付。基线main `8a3ce572fb4b534cb4308db4c5f7c356cea5332b`，工作分支`codex/x86_64-har`。

## 用户目标
在main基础上补充x86_64可用的完整Player HAR，提供CI原包地址并同步Todoist。当前ARM64产物不变；不使用旧桥或只有NAPI探针的产物冒充完整播放。

## 需求与验收
- R1：x86_64桥必须由当前Player源码编译并链接可运行的mpv及匹配FFmpeg依赖；只有ELF架构正确或HAR编译通过不算播放支持。
- R2：SDK来源必须固定提交/哈希，包含六库、匹配头文件/pkg-config、配置/能力、许可证及依赖闭包。FFmpeg构建归ohos_ijkplayer，Player只读消费，不替其构建或发布。
- R3：保留Spec017 preserve-host、音频打断/手动恢复、尺寸、旋转和播完合同。x86_64硬解能力按SDK与目标实际能力声明；软件路径不假装OHCodec硬解，不能用无行为stub伪造恢复接口。
- R4：缺库、错架构、SONAME/依赖冲突、旧桥/探针、配置未知或哈希不匹配必须在交付前拒绝。保持ARM64完整九库；最终双架构内容和每库哈希显式记录。
- R5：普通分支由iMac自托管Actions交付原始HAR；记录实际runner、源提交、HAR与每库哈希及消费方式，不重打包Player。
- R6：分层记录主机、消费构建、x86_64模拟器的正常播放/暂停恢复/seek/关闭重开/坏片续播。模拟器不替代API19 TV硬解验收，#93不并入本次完成结论。

## 当前限制
上游master 32887363的受控producer合同和当前恢复SDK仅ARM64。上游README存在基础FFmpeg8 x86构建说明，但未取得当前可消费的完整x86 SDK。旧TV六库为x86 ELF，缺当前OHCodec扩展符号及受控headers/pkg-config/身份包，不能直接替换当前核心。可行的纯软件分支仍须先获得真实匹配SDK并验证能力，不因缺OHCodec就断言x86软件播放不可行。

负责会话：[修复 issue #89](thread://01a1bccc-e2cc-7a13-8cd6-31aae7079fb0?hostId=local)；thread ID `01a1bccc-e2cc-7a13-8cd6-31aae7079fb0`；host `local`；更新2026-11-15。
