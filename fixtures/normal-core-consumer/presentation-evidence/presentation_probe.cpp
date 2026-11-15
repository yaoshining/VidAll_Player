#include "bounded_enumeration.h"
#include <napi/native_api.h>
#include <vulkan/vulkan.h>
#include <EGL/egl.h>
#include <sstream>
#include <string>

static std::string Quote(const char* s) {
    std::string out="\"";
    for (;*s;++s) { if (*s=='"'||*s=='\\') out+='\\'; if (static_cast<unsigned char>(*s)>=32) out+=*s; }
    return out+'"';
}
static std::string Probe() {
    VkApplicationInfo app{};app.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO;app.pApplicationName="Spec017PresentationCapability";app.apiVersion=VK_API_VERSION_1_0;
    VkInstanceCreateInfo create{};create.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;create.pApplicationInfo=&app;
    VkInstance instance=VK_NULL_HANDLE;const VkResult rc=vkCreateInstance(&create,nullptr,&instance);
    if (rc!=VK_SUCCESS) return "{\"querySucceeded\":false,\"stage\":\"create-instance\",\"error\":"+std::to_string(rc)+"}";
    struct Guard { VkInstance i;~Guard(){vkDestroyInstance(i,nullptr);} } guard{instance};
    auto devices=BoundedEnumerate<VkPhysicalDevice>([&](uint32_t* n,VkPhysicalDevice* p){return vkEnumeratePhysicalDevices(instance,n,p);},16);
    if (!devices.ok) return "{\"querySucceeded\":false,\"stage\":\"physical-devices\",\"error\":"+std::to_string(devices.error)+"}";
    std::ostringstream out;out<<"{\"querySucceeded\":true,\"actualPresentationMeasured\":false,\"devices\":[";
    bool first=true;
    for (auto device:devices.values) {
        if(!first)out<<',';first=false;
        VkPhysicalDeviceProperties prop{};vkGetPhysicalDeviceProperties(device,&prop);
        auto exts=BoundedEnumerate<VkExtensionProperties>([&](uint32_t* n,VkExtensionProperties* p){return vkEnumerateDeviceExtensionProperties(device,nullptr,n,p);},1024);
        out<<"{\"name\":"<<Quote(prop.deviceName)<<",\"vendorId\":"<<prop.vendorID<<",\"deviceId\":"<<prop.deviceID<<",\"apiVersion\":"<<prop.apiVersion<<",\"driverVersion\":"<<prop.driverVersion<<",\"extensionQuerySucceeded\":"<<(exts.ok?"true":"false")<<",\"error\":"<<exts.error<<",\"extensions\":[";
        bool firstExt=true;for(const auto& ext:exts.values){if(!firstExt)out<<',';firstExt=false;out<<Quote(ext.extensionName);}out<<"]}";
    }
    // 只读现有display；不初始化/终止进程共享EGL状态，不创建或改写Player surface。
    EGLDisplay display=eglGetDisplay(EGL_DEFAULT_DISPLAY);
    const char* eglExtensions=display==EGL_NO_DISPLAY?nullptr:eglQueryString(display,EGL_EXTENSIONS);
    const EGLint eglError=eglGetError();
    out<<"],\"eglReadOnly\":{\"querySucceeded\":"<<(eglExtensions?"true":"false")<<",\"error\":"<<eglError
       <<",\"extensions\":"<<Quote(eglExtensions?eglExtensions:"")
       <<",\"frameTimestampsFunction\":"<<(eglGetProcAddress("eglGetFrameTimestampsANDROID")?"true":"false")
       <<",\"frameSupportedFunction\":"<<(eglGetProcAddress("eglGetFrameTimestampSupportedANDROID")?"true":"false")<<"}}";
    return out.str();
}
struct Work { napi_async_work work=nullptr;napi_deferred deferred=nullptr;std::string result; };
static napi_value Query(napi_env env,napi_callback_info) {
    auto* data=new Work;napi_value promise;
    if(napi_create_promise(env,&data->deferred,&promise)!=napi_ok){delete data;return nullptr;}
    napi_value name;napi_create_string_utf8(env,"presentationCapabilities",NAPI_AUTO_LENGTH,&name);
    auto execute=[](napi_env,void* p){auto* d=static_cast<Work*>(p);try{d->result=Probe();}catch(...){d->result="{\"querySucceeded\":false,\"stage\":\"exception\"}";}};
    auto complete=[](napi_env e,napi_status status,void* p){auto* d=static_cast<Work*>(p);napi_value value;if(status==napi_ok){napi_create_string_utf8(e,d->result.c_str(),d->result.size(),&value);napi_resolve_deferred(e,d->deferred,value);}else{napi_create_string_utf8(e,"presentation query cancelled",NAPI_AUTO_LENGTH,&value);napi_reject_deferred(e,d->deferred,value);}napi_delete_async_work(e,d->work);delete d;};
    if(napi_create_async_work(env,nullptr,name,execute,complete,data,&data->work)!=napi_ok || napi_queue_async_work(env,data->work)!=napi_ok){
        napi_value error;napi_create_string_utf8(env,"presentation query scheduling failed",NAPI_AUTO_LENGTH,&error);napi_reject_deferred(env,data->deferred,error);if(data->work)napi_delete_async_work(env,data->work);delete data;
    }
    return promise;
}
static napi_value Init(napi_env env,napi_value exports){napi_property_descriptor p={"query",nullptr,Query,nullptr,nullptr,nullptr,napi_default,nullptr};napi_define_properties(env,exports,1,&p);return exports;}
static napi_module module={1,0,nullptr,Init,"presentation_probe",nullptr,{0}};
extern "C" __attribute__((constructor)) void RegisterPresentationProbe(){napi_module_register(&module);}
