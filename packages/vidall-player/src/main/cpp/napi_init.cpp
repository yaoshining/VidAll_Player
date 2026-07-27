#include <napi/native_api.h>

namespace {

napi_ref g_callback = nullptr;

napi_value CreateString(napi_env env, const char* value)
{
    napi_value result = nullptr;
    napi_create_string_utf8(env, value, NAPI_AUTO_LENGTH, &result);
    return result;
}

napi_value Ping(napi_env env, napi_callback_info)
{
    return CreateString(env, "har-native-ping");
}

napi_value SetCallback(napi_env env, napi_callback_info info)
{
    size_t argc = 1;
    napi_value args[1] = {nullptr};
    napi_get_cb_info(env, info, &argc, args, nullptr, nullptr);
    if (argc != 1) {
        napi_throw_type_error(env, nullptr, "callback is required");
        return nullptr;
    }
    napi_valuetype type = napi_undefined;
    napi_typeof(env, args[0], &type);
    if (type != napi_function) {
        napi_throw_type_error(env, nullptr, "callback must be a function");
        return nullptr;
    }
    if (g_callback != nullptr) {
        napi_delete_reference(env, g_callback);
        g_callback = nullptr;
    }
    napi_create_reference(env, args[0], 1, &g_callback);
    napi_value global = nullptr;
    napi_get_global(env, &global);
    napi_value payload = CreateString(env, "har-native-callback");
    napi_call_function(env, global, args[0], 1, &payload, nullptr);
    return CreateString(env, "callback-dispatched");
}

napi_value Init(napi_env env, napi_value exports)
{
    napi_property_descriptor descriptors[] = {
        {"ping", nullptr, Ping, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setCallback", nullptr, SetCallback, nullptr, nullptr, nullptr, napi_default, nullptr},
    };
    napi_define_properties(env, exports, sizeof(descriptors) / sizeof(descriptors[0]), descriptors);
    return exports;
}

} // namespace

NAPI_MODULE(vidall_player_native, Init)
