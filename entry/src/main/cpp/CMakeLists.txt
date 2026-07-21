cmake_minimum_required(VERSION 3.4.1)
project(vidall_player_napi)

set(NATIVE_ROOT ${CMAKE_CURRENT_SOURCE_DIR})
add_library(entry SHARED napi_bridge.cpp)

target_compile_features(entry PRIVATE cxx_std_17)
target_link_libraries(entry PUBLIC libace_napi.z.so libace_ndk.z.so libhilog_ndk.z.so)

if(OHOS_ARCH STREQUAL "arm64-v8a")
  set(LIBMPV_ROOT ${NATIVE_ROOT}/third_party/libmpv/arm64-v8a)
  add_library(mpv SHARED IMPORTED)
  set_target_properties(mpv PROPERTIES
    IMPORTED_LOCATION ${LIBMPV_ROOT}/libmpv.so)
  target_include_directories(entry PRIVATE ${LIBMPV_ROOT}/include)
  target_compile_definitions(entry PRIVATE VIDALL_MPV_AVAILABLE=1)
  target_link_libraries(entry PRIVATE mpv EGL GLESv3 native_window dl)
else()
  target_compile_definitions(entry PRIVATE VIDALL_MPV_AVAILABLE=0)
endif()
