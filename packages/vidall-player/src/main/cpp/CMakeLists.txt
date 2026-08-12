# G2 加载边界：arm64-v8a 绑定 libmpv 原生产物（VIDALL_MPV_AVAILABLE=1），
# x86_64 仅 NAPI probe（VIDALL_MPV_AVAILABLE=0），不表述为真实播放能力。
# libmpv.so SHA-256=dfa7724b0ba520fed6e4fe3e39c2bb73dc01cd50b69ca09efc93f729e07cd151
# 详细边界见 release/manifests/candidate-003-libmpv-player-har.json
cmake_minimum_required(VERSION 3.4.1)
project(vidall_player_native)

set(CMAKE_SKIP_RPATH TRUE)

add_library(vidall_player_native SHARED napi_init.cpp)
target_compile_features(vidall_player_native PRIVATE cxx_std_17)
target_link_libraries(vidall_player_native PUBLIC libace_napi.z.so libace_ndk.z.so libhilog_ndk.z.so)

if(OHOS_ARCH STREQUAL "arm64-v8a")
  set(LIBMPV_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../../entry/src/main/cpp/third_party/libmpv/arm64-v8a)
  add_library(mpv SHARED IMPORTED)
  set_target_properties(mpv PROPERTIES IMPORTED_LOCATION ${LIBMPV_ROOT}/libmpv.so)
  target_include_directories(vidall_player_native PRIVATE ${LIBMPV_ROOT}/include)
  target_compile_definitions(vidall_player_native PRIVATE VIDALL_MPV_AVAILABLE=1)
  target_link_libraries(vidall_player_native PRIVATE mpv native_window EGL GLESv3)
else()
  target_compile_definitions(vidall_player_native PRIVATE VIDALL_MPV_AVAILABLE=0)
endif()
