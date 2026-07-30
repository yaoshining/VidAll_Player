// T045/T046 字幕渲染测试
// 覆盖：native 唯一渲染路径、CJK 字体降级、双向文字、字体缺失、异常编码

#include "../media/SubtitleRenderer.h"
#include <cstdio>
#include <string>
#include <vector>

namespace {

int g_tests_passed = 0;
int g_tests_failed = 0;

void check(bool condition, const char* file, int line, const char* msg) {
    if (!condition) {
        std::fprintf(stderr, "FAIL %s:%d: %s\n", file, line, msg);
        g_tests_failed++;
    } else {
        g_tests_passed++;
    }
}

#define CHECK(cond, msg) check((cond), __FILE__, __LINE__, (msg))

} // anonymous namespace

// ══════════════════════════════════════════════════════════════════
// 1. ArkTS overlay 互斥：唯一渲染路径禁止 ArkTS overlay
// ══════════════════════════════════════════════════════════════════

void test_arkts_overlay_forbidden() {
    CHECK(vidall::SubtitleRenderer::isArkTsOverlayForbidden(),
          "ArkTS overlay must be forbidden for subtitle rendering");
}

// ══════════════════════════════════════════════════════════════════
// 2. 图形字幕（PGS）判定为 Bitmap
// ══════════════════════════════════════════════════════════════════

void test_pgs_bitmap_verdict() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "pgs";

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Bitmap,
          "PGS should be Bitmap verdict");
    CHECK(result.degradation == vidall::DegradationReason::None,
          "PGS should have no degradation reason");
}

// ══════════════════════════════════════════════════════════════════
// 3. 图形字幕（VOBsub）判定为 Bitmap
// ══════════════════════════════════════════════════════════════════

void test_vobsub_bitmap_verdict() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "vobsub";

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Bitmap,
          "VOBsub should be Bitmap verdict");
}

// ══════════════════════════════════════════════════════════════════
// 4. SRT 英文字幕判定为 Renderable
// ══════════════════════════════════════════════════════════════════

void test_srt_english_renderable() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "srt";
    req.language = "en";

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Renderable,
          "SRT English should be Renderable");
    CHECK(result.degradation == vidall::DegradationReason::None,
          "SRT English should have no degradation");
}

// ══════════════════════════════════════════════════════════════════
// 5. ASS 中文字幕降级为 Degraded（CJK 字体缺失）
// ══════════════════════════════════════════════════════════════════

void test_ass_cjk_degraded() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "ass";
    req.language = "zh-Hans";

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Degraded,
          "ASS Chinese should be Degraded (CJK font missing)");
    CHECK(result.degradation == vidall::DegradationReason::CjkFontMissing,
          "ASS Chinese degradation reason should be CjkFontMissing");
    CHECK(result.font.isCjkFallback,
          "ASS Chinese font should be CJK fallback");
}

// ══════════════════════════════════════════════════════════════════
// 6. 日语字幕降级为 Degraded
// ══════════════════════════════════════════════════════════════════

void test_srt_japanese_degraded() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "srt";
    req.language = "ja";

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Degraded,
          "SRT Japanese should be Degraded (CJK font missing)");
    CHECK(result.degradation == vidall::DegradationReason::CjkFontMissing,
          "SRT Japanese degradation should be CjkFontMissing");
}

// ══════════════════════════════════════════════════════════════════
// 7. 双向文字（阿拉伯语）降级为 Degraded
// ══════════════════════════════════════════════════════════════════

void test_bidi_degraded() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "srt";
    req.language = "ar";
    req.requiresBiDi = true;

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Degraded,
          "Bidirectional text should be Degraded");
    CHECK(result.degradation == vidall::DegradationReason::BiDiUnsupported,
          "Bidirectional degradation should be BiDiUnsupported");
}

// ══════════════════════════════════════════════════════════════════
// 8. 异常编码降级为 Degraded
// ══════════════════════════════════════════════════════════════════

void test_abnormal_encoding_degraded() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "srt";
    req.language = "en";
    req.encoding = "gbk";

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Degraded,
          "GBK encoding should be Degraded");
    CHECK(result.degradation == vidall::DegradationReason::EncodingAbnormal,
          "GBK degradation should be EncodingAbnormal");
}

// ══════════════════════════════════════════════════════════════════
// 9. UTF-8 编码不降级
// ══════════════════════════════════════════════════════════════════

void test_utf8_no_degradation() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "srt";
    req.language = "en";
    req.encoding = "utf-8";

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Renderable,
          "UTF-8 English SRT should be Renderable");
}

// ══════════════════════════════════════════════════════════════════
// 10. 不支持的格式判定为 Unsupported
// ══════════════════════════════════════════════════════════════════

void test_unsupported_format() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "dvb";

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Unsupported,
          "DVB should be Unsupported");
}

// ══════════════════════════════════════════════════════════════════
// 11. isBitmapFormat / isTextFormat 分类
// ══════════════════════════════════════════════════════════════════

void test_format_classification() {
    CHECK(vidall::SubtitleRenderer::isBitmapFormat("pgs"),
          "PGS should be bitmap format");
    CHECK(vidall::SubtitleRenderer::isBitmapFormat("vobsub"),
          "VOBsub should be bitmap format");
    CHECK(!vidall::SubtitleRenderer::isBitmapFormat("srt"),
          "SRT should not be bitmap format");

    CHECK(vidall::SubtitleRenderer::isTextFormat("srt"),
          "SRT should be text format");
    CHECK(vidall::SubtitleRenderer::isTextFormat("ass"),
          "ASS should be text format");
    CHECK(vidall::SubtitleRenderer::isTextFormat("ssa"),
          "SSA should be text format");
    CHECK(vidall::SubtitleRenderer::isTextFormat("webvtt"),
          "WebVTT should be text format");
    CHECK(!vidall::SubtitleRenderer::isTextFormat("pgs"),
          "PGS should not be text format");
}

// ══════════════════════════════════════════════════════════════════
// 12. WebVTT 英文 Renderable
// ══════════════════════════════════════════════════════════════════

void test_webvtt_english_renderable() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "webvtt";
    req.language = "en";

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Renderable,
          "WebVTT English should be Renderable");
}

// ══════════════════════════════════════════════════════════════════
// 13. 字体发现：非 CJK 语言找到非回退字体
// ══════════════════════════════════════════════════════════════════

void test_font_discovery_non_cjk() {
    vidall::SubtitleRenderer renderer;
    auto result = renderer.discoverFont("en");

    CHECK(result.found, "English font should be found");
    CHECK(!result.isCjkFallback, "English font should not be CJK fallback");
    CHECK(!result.path.empty(), "Font path should not be empty");
}

// ══════════════════════════════════════════════════════════════════
// 14. 字体发现：CJK 语言使用回退字体
// ══════════════════════════════════════════════════════════════════

void test_font_discovery_cjk() {
    vidall::SubtitleRenderer renderer;
    auto result = renderer.discoverFont("zh-Hans");

    CHECK(result.found, "CJK font should be found (as fallback)");
    CHECK(result.isCjkFallback, "CJK font should be marked as fallback");
    CHECK(!result.path.empty(), "CJK font path should not be empty");
}

// ══════════════════════════════════════════════════════════════════
// 15. clear 后可重新使用
// ══════════════════════════════════════════════════════════════════

void test_clear_and_reuse() {
    vidall::SubtitleRenderer renderer;
    renderer.clear();

    vidall::SubtitleRenderRequest req;
    req.format = "srt";
    req.language = "en";

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Renderable,
          "Renderer should work after clear()");
}

// ══════════════════════════════════════════════════════════════════
// 16. 韩语 CJK 降级
// ══════════════════════════════════════════════════════════════════

void test_korean_cjk_degraded() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "srt";
    req.language = "ko";

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Degraded,
          "Korean should be Degraded (CJK font missing)");
    CHECK(result.degradation == vidall::DegradationReason::CjkFontMissing,
          "Korean degradation should be CjkFontMissing");
}

// ══════════════════════════════════════════════════════════════════
// 17. 结果消息非空
// ══════════════════════════════════════════════════════════════════

void test_result_message_not_empty() {
    vidall::SubtitleRenderer renderer;

    vidall::SubtitleRenderRequest req;
    req.format = "srt";
    req.language = "en";

    auto result = renderer.evaluate(req);
    CHECK(!result.message.empty(), "Render result message should not be empty");

    req.format = "pgs";
    result = renderer.evaluate(req);
    CHECK(!result.message.empty(), "Bitmap result message should not be empty");

    req.format = "dvb";
    result = renderer.evaluate(req);
    CHECK(!result.message.empty(), "Unsupported result message should not be empty");
}

// ══════════════════════════════════════════════════════════════════
// 18. 默认编码（空字符串）视为 UTF-8 不降级
// ══════════════════════════════════════════════════════════════════

void test_default_encoding_no_degradation() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "srt";
    req.language = "en";
    // encoding 默认为空字符串

    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Renderable,
          "Default encoding should be treated as UTF-8");
}

// ══════════════════════════════════════════════════════════════════
// 19. 大小写不敏感格式判定
// ══════════════════════════════════════════════════════════════════

void test_case_insensitive_format() {
    // isBitmapFormat 大小写不敏感
    CHECK(vidall::SubtitleRenderer::isBitmapFormat("PGS"),
          "PGS (uppercase) should be bitmap format");
    CHECK(vidall::SubtitleRenderer::isBitmapFormat("VobSub"),
          "VobSub (mixed case) should be bitmap format");

    // isTextFormat 大小写不敏感
    CHECK(vidall::SubtitleRenderer::isTextFormat("SRT"),
          "SRT (uppercase) should be text format");
    CHECK(vidall::SubtitleRenderer::isTextFormat("Ass"),
          "Ass (mixed case) should be text format");
    CHECK(vidall::SubtitleRenderer::isTextFormat("SSA"),
          "SSA (uppercase) should be text format");
    CHECK(vidall::SubtitleRenderer::isTextFormat("WEBVTT"),
          "WEBVTT (uppercase) should be text format");

    // evaluate 大小写不敏感
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;
    req.format = "PGS";
    auto result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Bitmap,
          "PGS (uppercase) should produce Bitmap verdict");

    req.format = "SRT";
    req.language = "en";
    result = renderer.evaluate(req);
    CHECK(result.verdict == vidall::SubtitleRenderVerdict::Renderable,
          "SRT (uppercase) should produce Renderable verdict");
}

// ══════════════════════════════════════════════════════════════════
// 20. 结果消息包含中英文
// ══════════════════════════════════════════════════════════════════

void test_bilingual_messages() {
    vidall::SubtitleRenderer renderer;
    vidall::SubtitleRenderRequest req;

    // Bitmap 消息含中文
    req.format = "pgs";
    auto result = renderer.evaluate(req);
    CHECK(result.message.find("图形字幕") != std::string::npos,
          "Bitmap message should contain Chinese text");

    // Renderable 消息含中文
    req.format = "srt";
    req.language = "en";
    result = renderer.evaluate(req);
    CHECK(result.message.find("可经") != std::string::npos,
          "Renderable message should contain Chinese text");
}

// ══════════════════════════════════════════════════════════════════
// 21. BCP-47 前缀边界：非 CJK 语言不被误判
// ══════════════════════════════════════════════════════════════════

void test_bcp47_prefix_boundary() {
    // "kok" (Konkani) 不应被 "ko" 前缀误判为 CJK
    CHECK(!vidall::SubtitleRenderer::isCjkLanguage("kok"),
          "\"kok\" (Konkani) should not be detected as CJK");
    // "ko" 本身应被检测为 CJK
    CHECK(vidall::SubtitleRenderer::isCjkLanguage("ko"),
          "\"ko\" should be detected as CJK");
    // "ko-KR" 应被检测为 CJK
    CHECK(vidall::SubtitleRenderer::isCjkLanguage("ko-KR"),
          "\"ko-KR\" should be detected as CJK");

    // RTL: "he" (Hebrew) vs "hel" (not a real code but test boundary)
    CHECK(vidall::SubtitleRenderer::isRtlLanguage("ar"),
          "\"ar\" should be detected as RTL");
    CHECK(!vidall::SubtitleRenderer::isRtlLanguage("art"),
          "\"art\" should not be detected as RTL");
    CHECK(vidall::SubtitleRenderer::isRtlLanguage("ar-SA"),
          "\"ar-SA\" should be detected as RTL");
}

int main() {
    test_arkts_overlay_forbidden();
    test_pgs_bitmap_verdict();
    test_vobsub_bitmap_verdict();
    test_srt_english_renderable();
    test_ass_cjk_degraded();
    test_srt_japanese_degraded();
    test_bidi_degraded();
    test_abnormal_encoding_degraded();
    test_utf8_no_degradation();
    test_unsupported_format();
    test_format_classification();
    test_webvtt_english_renderable();
    test_font_discovery_non_cjk();
    test_font_discovery_cjk();
    test_clear_and_reuse();
    test_korean_cjk_degraded();
    test_result_message_not_empty();
    test_default_encoding_no_degradation();
    test_case_insensitive_format();
    test_bilingual_messages();
    test_bcp47_prefix_boundary();

    std::printf("\nsubtitle_rendering_test: %d passed, %d failed\n",
                g_tests_passed, g_tests_failed);
    return g_tests_failed > 0 ? 1 : 0;
}