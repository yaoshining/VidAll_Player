#ifndef VIDALL_DIAGNOSTICS_H
#define VIDALL_DIAGNOSTICS_H
#include <mpv/client.h>
#include <cmath>
#include <iomanip>
#include <locale>
#include <sstream>
#include <string>
namespace vidall::diagnostics {
enum class Kind { Number, IntegerString, Text, Flag, Redacted, Unsupported };
struct Spec { const char* key; const char* property; Kind kind; const char* unit; double scale; bool estimated; };
inline const Spec properties[] = {
#include "properties.inc"
};
struct Field {
    std::string status = "unavailable";
    std::string value;
    std::string reason;
};
inline std::string Quote(const std::string& value) {
    std::string out = "\"";
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') { out += '\\'; out += c; }
        else if (c < 32) { const char* hex = "0123456789abcdef"; out += "\\u00"; out += hex[c >> 4]; out += hex[c & 15]; }
        else out += c;
    }
    return out + "\"";
}
inline std::string Number(double value) {
    std::ostringstream out; out.imbue(std::locale::classic()); out << std::setprecision(17) << value; return out.str();
}
inline Field Convert(const Spec& spec, int error, const mpv_node& node) {
    if (spec.kind == Kind::Unsupported) return {"unsupported", "", "absent-in-locked-version"};
    if (spec.kind == Kind::Redacted) return {"unavailable", "", "redacted"};
    if (error == MPV_ERROR_PROPERTY_NOT_FOUND) return {"unsupported", "", "property-not-found"};
    if (error == MPV_ERROR_PROPERTY_UNAVAILABLE) return {"unavailable", "", "not-ready"};
    if (error < 0) return {"error", "", "read-failed"};
    if (node.format == MPV_FORMAT_NONE) return {"unavailable", "", "no-value"};
    if (spec.kind == Kind::Text && node.format == MPV_FORMAT_STRING) {
        if (!node.u.string || !*node.u.string) return {"unavailable", "", "no-value"};
        const std::string s(node.u.string);
        // 只允许受控技术名称。任意媒体标题/文件名无法证明无凭据，固定隐去。
        if (s.size() > 160 || s.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-. +(),[]") != std::string::npos)
            return {"unavailable", "", "redacted"};
        return {"available", Quote(s), ""};
    }
    if (spec.kind == Kind::Flag && node.format == MPV_FORMAT_FLAG)
        return {"available", node.u.flag ? "true" : "false", ""};
    if (spec.kind == Kind::IntegerString && node.format == MPV_FORMAT_INT64) {
        if (node.u.int64 < 0) return {"error", "", "invalid-value"};
        return {"available", Quote(std::to_string(node.u.int64)), ""};
    }
    if (spec.kind == Kind::Number && (node.format == MPV_FORMAT_DOUBLE || node.format == MPV_FORMAT_INT64)) {
        if (node.format == MPV_FORMAT_INT64 && (node.u.int64 > 9007199254740991LL || node.u.int64 < -9007199254740991LL))
            return {"error", "", "unsafe-integer"};
        double n = (node.format == MPV_FORMAT_DOUBLE ? node.u.double_ : static_cast<double>(node.u.int64)) * spec.scale;
        if (!std::isfinite(n) || std::abs(n) > 9007199254740991.0) return {"error", "", "invalid-value"};
        return {"available", Number(n), ""};
    }
    return {"error", "", "type-mismatch"};
}
inline std::string Json(const Spec& spec, const Field& field) {
    std::string out = "{\"status\":" + Quote(field.status) + ",\"unit\":" + Quote(spec.unit) +
        ",\"source\":" + Quote(spec.property) + ",\"estimated\":" + (spec.estimated ? "true" : "false");
    if (!field.value.empty()) out += ",\"value\":" + field.value;
    if (!field.reason.empty()) out += ",\"reason\":" + Quote(field.reason);
    return out + "}";
}
}
#endif
