#include <napi/native_api.h>

namespace {

napi_ref g_callback = nullptr;

bool Check(napi_env env, napi_status status, const char* operation)
{
    if (status == napi_ok) {
        return true;
    }
    napi_throw_error(env, nullptr, operation);
    return false;
}

napi_value CreateString(napi_env env, const char* value)
{
    napi_value result = nullptr;
    if (!Check(env, napi_create_string_utf8(env, value, NAPI_AUTO_LENGTH, &result), "Failed to create result string.")) {
        return nullptr;
    }
    return result;
}

void CleanupCallback(void* data)
{
    napi_env env = static_cast<napi_env>(data);
    if (g_callback != nullptr) {
        napi_delete_reference(env, g_callback);
        g_callback = nullptr;
    }
}

napi_value Ping(napi_env env, napi_callback_info)
{
    return CreateString(env, "har-native-ping");
}

napi_value SetCallback(napi_env env, napi_callback_info info)
{
    size_t argc = 1;
    napi_value args[1] = {nullptr};
    if (!Check(env, napi_get_cb_info(env, info, &argc, args, nullptr, nullptr), "Failed to read callback argument.")) {
        return nullptr;
    }
    if (argc != 1) {
        napi_throw_type_error(env, nullptr, "callback is required");
        return nullptr;
    }
    napi_valuetype type = napi_undefined;
    if (!Check(env, napi_typeof(env, args[0], &type), "Failed to inspect callback argument.")) {
        return nullptr;
    }
    if (type != napi_function) {
        napi_throw_type_error(env, nullptr, "callback must be a function");
        return nullptr;
    }
    if (g_callback != nullptr) {
        if (!Check(env, napi_delete_reference(env, g_callback), "Failed to replace callback reference.")) {
            return nullptr;
        }
        g_callback = nullptr;
    }
    if (!Check(env, napi_create_reference(env, args[0], 1, &g_callback), "Failed to retain callback reference.")) {
        return nullptr;
    }
    napi_value global = nullptr;
    if (!Check(env, napi_get_global(env, &global), "Failed to get JavaScript global object.")) {
        return nullptr;
    }
    napi_value payload = CreateString(env, "har-native-callback");
    if (payload == nullptr) {
        return nullptr;
    }
    if (!Check(env, napi_call_function(env, global, args[0], 1, &payload, nullptr), "Callback invocation failed.")) {
        return nullptr;
    }
    return CreateString(env, "callback-dispatched");
}

napi_value Init(napi_env env, napi_value exports)
{
    napi_property_descriptor descriptors[] = {
        {"ping", nullptr, Ping, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"setCallback", nullptr, SetCallback, nullptr, nullptr, nullptr, napi_default, nullptr},
    };
    if (!Check(env, napi_define_properties(env, exports, sizeof(descriptors) / sizeof(descriptors[0]), descriptors),
            "Failed to define native probe exports.")) {
        return nullptr;
    }
    if (!Check(env, napi_add_env_cleanup_hook(env, CleanupCallback, env), "Failed to register native probe cleanup.")) {
        return nullptr;
    }
    return exports;
}

} // namespace

NAPI_MODULE(vidall_player_native, Init)
