#include "SubtitleRenderer.h"
#include <algorithm>
#include <cctype>

namespace {

std::string toLower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(),
        [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return value;
}

} // namespace

namespace vidall {

// T045/T046 字幕渲染实现：唯一路径、CJK 降级、双向文字、异常编码。
// 字体发现当前使用硬编码路径；T046 后续迭代将加载 fonts.json 配置。

SubtitleRenderResult SubtitleRenderer::evaluate(const SubtitleRenderRequest& request) {
    SubtitleRenderResult result;

    // 图形字幕：不走 libass 管线
    if (isBitmapFormat(request.format)) {
        result.verdict = SubtitleRenderVerdict::Bitmap;
        result.message = "图形字幕，不经 libass 渲染 (Bitmap subtitle, not rendered via libass)";
        return result;
    }

    // 不支持的格式
    if (!isTextFormat(request.format)) {
        result.verdict = SubtitleRenderVerdict::Unsupported;
        result.message = "首期不支持的字幕格式 (Unsupported subtitle format in first release)";
        return result;
    }

    // 文本字幕：评估字体可用性
    result.font = discoverFont(request.language);

    // 异常编码：非 UTF-8 在首期标记为 Degraded
    if (!request.encoding.empty() && request.encoding != "utf-8" && request.encoding != "UTF-8") {
        result.verdict = SubtitleRenderVerdict::Degraded;
        result.degradation = DegradationReason::EncodingAbnormal;
        result.message = "降级：非 UTF-8 编码首期未完全支持 (Degraded: non-UTF-8 encoding not fully supported in first release)";
        return result;
    }

    // 双向文字：首期标记为 Degraded
    if (request.requiresBiDi) {
        result.verdict = SubtitleRenderVerdict::Degraded;
        result.degradation = DegradationReason::BiDiUnsupported;
        result.message = "降级：双向文字首期未完全支持 (Degraded: bidirectional text not fully supported in first release)";
        return result;
    }

    // CJK 字体缺失：降级
    if (result.font.isCjkFallback) {
        result.verdict = SubtitleRenderVerdict::Degraded;
        result.degradation = DegradationReason::CjkFontMissing;
        result.message = "降级：CJK 字体缺失，使用回退 (Degraded: CJK font missing, using fallback)";
        return result;
    }

    // 正常渲染
    result.verdict = SubtitleRenderVerdict::Renderable;
    result.message = "可经 libass 渲染 (Renderable via libass)";
    return result;
}

FontDiscoveryResult SubtitleRenderer::discoverFont(const std::string& language) {
    FontDiscoveryResult result;

    // T046 将从 fonts.json 和系统字体目录查找。
    // 当前红阶段：CJK 语言标记为缺失字体（使用回退），非 CJK 标记为可用。
    if (isCjkLanguage(language)) {
        result.found = true;
        result.isCjkFallback = true;
        result.family = "sans-serif";
        result.path = "/system/fonts/NotoSansCJK-Regular.ttc";
    } else {
        result.found = true;
        result.isCjkFallback = false;
        result.family = "sans-serif";
        result.path = "/system/fonts/NotoSans-Regular.ttf";
    }
    return result;
}

bool SubtitleRenderer::isBitmapFormat(const std::string& format) {
    const auto lower = toLower(format);
    return lower == "pgs" || lower == "vobsub";
}

bool SubtitleRenderer::isTextFormat(const std::string& format) {
    const auto lower = toLower(format);
    return lower == "srt" || lower == "ass" || lower == "ssa" || lower == "webvtt";
}

bool SubtitleRenderer::isArkTsOverlayForbidden() {
    // ArkTS overlay 不得用于字幕渲染——唯一路径是 libass
    return true;
}

void SubtitleRenderer::clear() {
    configuredFontPaths_.clear();
}

bool SubtitleRenderer::isCjkLanguage(const std::string& language) {
    // BCP-47 CJK 语言标签，检查前缀后紧跟 '-' 或字符串结尾
    static const std::vector<std::string> cjkPrefixes = {
        "zh", "ja", "ko", "yue",
    };
    for (const auto& prefix : cjkPrefixes) {
        if (language.size() >= prefix.size() &&
            language.compare(0, prefix.size(), prefix) == 0) {
            if (language.size() == prefix.size() || language[prefix.size()] == '-') {
                return true;
            }
        }
    }
    return false;
}

bool SubtitleRenderer::isRtlLanguage(const std::string& language) {
    static const std::vector<std::string> rtlPrefixes = {
        "ar", "he", "fa", "ur",
    };
    for (const auto& prefix : rtlPrefixes) {
        if (language.size() >= prefix.size() &&
            language.compare(0, prefix.size(), prefix) == 0) {
            if (language.size() == prefix.size() || language[prefix.size()] == '-') {
                return true;
            }
        }
    }
    return false;
}

} // namespace vidall