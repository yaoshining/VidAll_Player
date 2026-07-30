#ifndef VIDALL_SUBTITLE_RENDERER_H
#define VIDALL_SUBTITLE_RENDERER_H

#include <cstdint>
#include <string>
#include <vector>

namespace vidall {

// 字幕渲染结论：区分"已识别"与"正确渲染"
enum class SubtitleRenderVerdict {
    Renderable,   // 文本字幕经 libass 正确渲染
    Degraded,     // 识别但渲染降级（CJK 字体缺失等）
    Bitmap,       // 图形字幕（PGS/VOBsub），不走 libass 管线
    Unsupported,  // 首期不支持的格式
};

// 字体发现结果
struct FontDiscoveryResult {
    std::string family;         // 匹配的字族名
    bool found = false;         // 是否在系统/配置路径中找到
    bool isCjkFallback = false; // 是否使用了 CJK 回退字体
    std::string path;           // 字体文件路径（空表示未找到）
};

// 渲染降级原因
enum class DegradationReason {
    None,
    CjkFontMissing,
    BiDiUnsupported,
    EncodingAbnormal,
};

// 字幕渲染请求
struct SubtitleRenderRequest {
    std::string format;           // "srt", "ass", "ssa", "webvtt", "pgs", "vobsub"
    std::string content;          // 原始字幕内容或 URI
    std::string language;         // BCP-47 语言标签（用于字体选择）
    bool requiresBiDi = false;    // 是否包含双向文字
    std::string encoding;         // 内容编码（默认 utf-8）
};

// 渲染结果
struct SubtitleRenderResult {
    SubtitleRenderVerdict verdict = SubtitleRenderVerdict::Renderable;
    DegradationReason degradation = DegradationReason::None;
    FontDiscoveryResult font;
    std::string message;          // 可消费的结构化结论
};

// SubtitleRenderer 保证唯一渲染路径：
// - 文本字幕（SRT/ASS/SSA/WebVTT）只经 libass 管线，不走 ArkTS overlay
// - 图形字幕（PGS/VOBsub）标记为 Bitmap，不参与 libass 渲染
// - CJK 字体缺失时降级为 Degraded，不伪造 Renderable
// - 双向文字在首期标记为 Degraded/BiDiUnsupported
// - 异常编码（非 UTF-8）在首期标记为 Degraded/EncodingAbnormal
class SubtitleRenderer {
public:
    SubtitleRenderer() = default;

    // 评估字幕渲染结论：根据格式、语言和字体可用性给出判定
    SubtitleRenderResult evaluate(const SubtitleRenderRequest& request);

    // 查询字体可用性
    FontDiscoveryResult discoverFont(const std::string& language);

    // 检查是否为图形字幕格式（PGS/VOBsub）
    static bool isBitmapFormat(const std::string& format);

    // 检查是否为文本字幕格式（SRT/ASS/SSA/WebVTT）
    static bool isTextFormat(const std::string& format);

    // 是否禁止 ArkTS overlay 渲染
    static bool isArkTsOverlayForbidden();

    // 重置状态
    void clear();

private:
    // 内部字体配置（T046 实现时从 fonts.json 加载）
    std::vector<std::string> configuredFontPaths_;

    static bool isCjkLanguage(const std::string& language);
    static bool isRtlLanguage(const std::string& language);
};

} // namespace vidall
#endif