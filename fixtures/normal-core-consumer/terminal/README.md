# 独立终局接管接缝

复制本分支到独立目录，正常 HAR 先冻结。仅在复制目录的 arm64 CMake 分支增加 terminal_fixture.cpp 与 `target_link_options(vidall_player_native PRIVATE -Wl,--wrap=mpv_ohcodec_terminal_snapshot)`。编译独立 HAR，包内八个正常核心库必须与冻结产物完全相同。主正常 HAR 不包含此文件/链接选项，也没有公开注入开关。

将本目录 Index.ets 用于独立消费者并链接该测试 HAR；首次健康 snapshot 后 5 秒返回测试记录。该接缝验证实际 SDK 通知、缓存/拒绝命令、宿主保屏释放及受控退出路径，不模拟真实 GPU hang。记录首次 terminal、host-exit-request 和外部有效进程/Ability/窗口查询；仅退出请求无法区分宿主 kill 与 native 截止兜底。
