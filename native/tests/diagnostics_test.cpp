#include "diagnostics.h"
#include <cassert>
#include <limits>
using namespace vidall::diagnostics;
int main() {
    for (const auto& spec : properties) {
        if (std::string(spec.key) == "durationMs" || std::string(spec.key) == "progressPercent") assert(spec.estimated);
    }
    Spec seconds{"positionMs", "time-pos", Kind::Number, "ms", 1000, false};
    mpv_node n{}; n.format = MPV_FORMAT_DOUBLE; n.u.double_ = 0;
    assert(Convert(seconds, 0, n).value == "0");
    n.u.double_ = 1.25;
    assert(Convert(seconds, 0, n).value == "1250");
    n.u.double_ = std::numeric_limits<double>::infinity();
    assert(Convert(seconds, 0, n).status == "error");
    n.u.double_ = std::numeric_limits<double>::quiet_NaN();
    assert(Convert(seconds, 0, n).status == "error");
    n.format = MPV_FORMAT_STRING; n.u.string = const_cast<char*>("123");
    assert(Convert(seconds, 0, n).status == "error");
    assert(Convert(seconds, MPV_ERROR_PROPERTY_UNAVAILABLE, n).status == "unavailable");
    assert(Convert(seconds, MPV_ERROR_PROPERTY_NOT_FOUND, n).status == "unsupported");
    assert(Convert(seconds, MPV_ERROR_GENERIC, n).status == "error");
    Spec bytes{"fileSize", "file-size", Kind::IntegerString, "byte", 1, false};
    n.format = MPV_FORMAT_INT64; n.u.int64 = INT64_MAX;
    assert(Convert(bytes, 0, n).value == "\"9223372036854775807\"");
    assert(Convert(seconds, 0, n).status == "error");
    Spec unsupported{"depth", "video-params/plane-depth", Kind::Unsupported, "bit", 1, false};
    assert(Convert(unsupported, 0, n).status == "unsupported");
    n.u.int64 = -1;
    assert(Convert(bytes, 0, n).status == "error");
    n.format = MPV_FORMAT_NONE;
    assert(Convert(seconds, 0, n).status == "unavailable");
    assert(Json(seconds, Convert(seconds, 0, n)).find("\"value\"") == std::string::npos);
    // 真机回归：demuxer-cache-state 只支持整张 NODE_MAP 读取，不支持斜杠子属性。
    Spec cache{"cacheForwardBytes", "demuxer-cache-state/fw-bytes", Kind::IntegerString, "byte", 1, true};
    mpv_node child{}; child.format = MPV_FORMAT_INT64; child.u.int64 = 0;
    char* keys[] = {const_cast<char*>("fw-bytes")};
    mpv_node_list list{1, &child, keys};
    mpv_node map{}; map.format = MPV_FORMAT_NODE_MAP; map.u.list = &list;
    assert(ConvertMapMember(cache, 0, map, "fw-bytes").value == "\"0\"");
    assert(ConvertMapMember(cache, 0, map, "file-cache-bytes").status == "unavailable");
    assert(ConvertMapMember(cache, MPV_ERROR_PROPERTY_UNAVAILABLE, map, "fw-bytes").status == "unavailable");
    map.format = MPV_FORMAT_STRING;
    assert(ConvertMapMember(cache, 0, map, "fw-bytes").status == "error");
    Spec flag{"paused", "pause", Kind::Flag, "boolean", 1, false};
    n.format = MPV_FORMAT_FLAG; n.u.flag = 0;
    assert(Convert(flag, 0, n).value == "false");
    Spec text{"codec", "codec", Kind::Text, "text", 1, false};
    n.format = MPV_FORMAT_STRING; n.u.string = const_cast<char*>("hevc");
    assert(Convert(text, 0, n).value == "\"hevc\"");
    n.u.string = const_cast<char*>("https://user:secret@host/a?token=abc");
    assert(Convert(text, 0, n).status == "unavailable");
    Spec sensitive{"filename", "filename", Kind::Redacted, "text", 1, false};
    assert(Convert(sensitive, 0, n).status == "unavailable");
    n.u.string = nullptr;
    assert(Convert(text, 0, n).status == "unavailable");
}
