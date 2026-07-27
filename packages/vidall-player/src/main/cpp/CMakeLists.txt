cmake_minimum_required(VERSION 3.4.1)
project(vidall_player_native)

add_library(vidall_player_native SHARED napi_init.cpp)
target_compile_features(vidall_player_native PRIVATE cxx_std_17)
target_link_libraries(vidall_player_native PUBLIC libace_napi.z.so)
