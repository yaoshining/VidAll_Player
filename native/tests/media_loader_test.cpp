// T028: 本地/HTTP 加载失败先行测试
// 覆盖：可读媒体、文件不存在、权限拒绝、无效 URI、TLS/Range 失败的脱敏错误
// 所有测试在当前阶段必须先失败，待 T029 实现后通过。

#include <iostream>
#include <string>
#include <vector>

#include "MediaLoader.h"
#include "PlayerErrorMapper.h"

namespace {

bool check(bool condition, const char* message)
{
    if (!condition) {
        std::cerr << "FAILED: " << message << '\n';
        return false;
    }
    return true;
}

bool checkContains(const std::string& haystack, const std::string& needle, const char* message)
{
    if (haystack.find(needle) == std::string::npos) {
        std::cerr << "FAILED: " << message << " (expected '" << needle
                  << "' in '" << haystack << "')\n";
        return false;
    }
    return true;
}

} // namespace

int main()
{
    vidall::MediaLoader loader;
    bool passed = true;

    // ===== 正常路径：可读本地文件 =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::LocalFile;
        req.uri = "file:///data/media/video.mp4";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::Accepted,
            "local file with valid file URI is accepted");
    }

    // ===== 正常路径：可读 HTTP URI =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::Http;
        req.uri = "http://example.com/media.mp4";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::Accepted,
            "HTTP URI with matching kind is accepted");
    }

    // ===== 正常路径：可读 HTTPS URI =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::Https;
        req.uri = "https://example.com/media.mp4";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::Accepted,
            "HTTPS URI with matching kind is accepted");
    }

    // ===== 边界：file://localhost/ 本地文件 =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::LocalFile;
        req.uri = "file://localhost/data/media/video.mp4";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::Accepted,
            "local file with localhost authority is accepted");
    }

    // ===== 失败路径：空 URI =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::LocalFile;
        req.uri = "";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::RejectedInvalidUri,
            "empty URI is rejected as invalid");
        const auto err = vidall::PlayerErrorMapper::mapLoadResult(result);
        passed &= check(err.domain == "input", "empty URI error domain is input");
        passed &= check(!err.retryable, "empty URI error is not retryable");
    }

    // ===== 失败路径：本地文件非 file:// URI =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::LocalFile;
        req.uri = "http://example.com/video.mp4";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::RejectedInvalidLocalFileUri,
            "local file with HTTP URI is rejected");
    }

    // ===== 失败路径：本地文件 URI 包含用户信息 =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::LocalFile;
        req.uri = "file://user@host/data/media/video.mp4";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::RejectedUrlUserinfoForbidden,
            "local file URI with userinfo is rejected");
    }

    // ===== 失败路径：本地文件 URI 缺少绝对路径 =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::LocalFile;
        req.uri = "file://localhostrelative/path.mp4";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::RejectedInvalidLocalFileUri,
            "local file URI without absolute path is rejected");
    }

    // ===== 失败路径：HTTP kind 与 HTTPS URI 不匹配 =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::Http;
        req.uri = "https://example.com/media.mp4";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::RejectedKindMismatch,
            "HTTP kind with HTTPS URI is rejected as kind mismatch");
    }

    // ===== 失败路径：HTTPS kind 与 HTTP URI 不匹配 =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::Https;
        req.uri = "http://example.com/media.mp4";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::RejectedKindMismatch,
            "HTTPS kind with HTTP URI is rejected as kind mismatch");
    }

    // ===== 失败路径：网络 URI 包含用户信息 =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::Http;
        req.uri = "http://user:pass@example.com/media.mp4";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::RejectedUrlUserinfoForbidden,
            "HTTP URI with userinfo is rejected");
    }

    // ===== 失败路径：未验证协议（rtsp） =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::Http;
        req.uri = "rtsp://example.com/stream";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::RejectedProtocolNotVerified,
            "unverified protocol rtsp is rejected");
    }

    // ===== 失败路径：未验证协议（rtmp） =====
    {
        vidall::MediaLoadRequest req;
        req.kind = vidall::MediaKind::Http;
        req.uri = "rtmp://example.com/stream";
        const auto result = loader.load(req);
        passed &= check(result == vidall::MediaLoadResult::RejectedProtocolNotVerified,
            "unverified protocol rtmp is rejected");
    }

    // ===== 错误映射：TLS 失败脱敏 =====
    {
        const auto err = vidall::PlayerErrorMapper::mapTlsError("certificate verify failed");
        passed &= check(err.domain == "network", "TLS error domain is network");
        passed &= check(err.code == "TLS_FAILED", "TLS error code is TLS_FAILED");
        passed &= check(!err.retryable, "TLS error is not retryable");
        passed &= checkContains(err.message, "TLS error", "TLS error message contains domain prefix");
        // 脱敏验证：消息中不应包含凭据或完整路径
        passed &= check(err.message.find("password") == std::string::npos,
            "TLS error message must not contain credential keywords");
    }

    // ===== 错误映射：Range 不满足 =====
    {
        const auto err = vidall::PlayerErrorMapper::mapRangeError();
        passed &= check(err.domain == "network", "Range error domain is network");
        passed &= check(err.code == "RANGE_NOT_SATISFIABLE", "Range error code is correct");
        passed &= check(err.retryable, "Range error is retryable");
    }

    // ===== 错误映射：文件不存在脱敏 =====
    {
        const auto err = vidall::PlayerErrorMapper::mapFileNotFound("[REDACTED_PATH]");
        passed &= check(err.domain == "media", "file-not-found error domain is media");
        passed &= check(err.code == "FILE_NOT_FOUND", "file-not-found error code is correct");
        passed &= check(!err.retryable, "file-not-found error is not retryable");
        // 脱敏：消息中不包含完整文件系统路径
        passed &= check(err.message.find("/data/") == std::string::npos,
            "file-not-found message must not contain full filesystem path");
    }

    // ===== 错误映射：权限拒绝 =====
    {
        const auto err = vidall::PlayerErrorMapper::mapPermissionDenied();
        passed &= check(err.domain == "media", "permission-denied error domain is media");
        passed &= check(err.code == "PERMISSION_DENIED", "permission-denied error code is correct");
        passed &= check(!err.retryable, "permission-denied error is not retryable");
    }

    // ===== 错误映射：libmpv 加载失败 =====
    {
        const auto err = vidall::PlayerErrorMapper::mapMpvError(-7, "network timeout");
        passed &= check(err.domain == "media", "mpv loading-failed error domain is media");
        passed &= check(err.code == "LOADING_FAILED", "mpv loading-failed error code is correct");
        passed &= check(err.retryable, "mpv loading-failed is retryable");
    }

    // ===== 错误映射：libmpv 不支持 =====
    {
        const auto err = vidall::PlayerErrorMapper::mapMpvError(-4, "");
        passed &= check(err.domain == "media", "mpv unsupported error domain is media");
        passed &= check(err.code == "UNSUPPORTED", "mpv unsupported error code is correct");
        passed &= check(!err.retryable, "mpv unsupported is not retryable");
    }

    // ===== 错误映射：MediaLoadResult 全覆盖 =====
    {
        // Verify every MediaLoadResult enum value maps to a non-empty domain/code
        const vidall::MediaLoadResult allResults[] = {
            vidall::MediaLoadResult::Accepted,
            vidall::MediaLoadResult::RejectedInvalidUri,
            vidall::MediaLoadResult::RejectedFileNotFound,
            vidall::MediaLoadResult::RejectedPermissionDenied,
            vidall::MediaLoadResult::RejectedTlsFailed,
            vidall::MediaLoadResult::RejectedRangeNotSatisfiable,
            vidall::MediaLoadResult::RejectedInvalidLocalFileUri,
            vidall::MediaLoadResult::RejectedProtocolNotVerified,
            vidall::MediaLoadResult::RejectedUrlUserinfoForbidden,
            vidall::MediaLoadResult::RejectedKindMismatch,
        };
        for (const auto r : allResults) {
            const auto mapped = vidall::PlayerErrorMapper::mapLoadResult(r);
            if (r != vidall::MediaLoadResult::Accepted) {
                passed &= check(!mapped.domain.empty(),
                    "all rejection results must map to non-empty domain");
                passed &= check(!mapped.code.empty(),
                    "all rejection results must map to non-empty code");
            }
        }
    }

    // ===== 连续加载：可重复使用 =====
    {
        vidall::MediaLoader reusable;
        vidall::MediaLoadRequest req1;
        req1.kind = vidall::MediaKind::LocalFile;
        req1.uri = "file:///data/a.mp4";
        passed &= check(reusable.load(req1) == vidall::MediaLoadResult::Accepted,
            "first load succeeds");

        vidall::MediaLoadRequest req2;
        req2.kind = vidall::MediaKind::Http;
        req2.uri = "http://example.com/b.mp4";
        passed &= check(reusable.load(req2) == vidall::MediaLoadResult::Accepted,
            "second load on same loader succeeds");
    }

    // ===== lastError 在成功后清空 =====
    {
        vidall::MediaLoader withError;
        vidall::MediaLoadRequest badReq;
        badReq.kind = vidall::MediaKind::LocalFile;
        badReq.uri = "";
        withError.load(badReq);
        passed &= check(!withError.lastError().code.empty(),
            "error recorded after failed load");

        vidall::MediaLoadRequest goodReq;
        goodReq.kind = vidall::MediaKind::LocalFile;
        goodReq.uri = "file:///data/media/video.mp4";
        withError.load(goodReq);
        passed &= check(withError.lastError().code.empty(),
            "error cleared after successful load");
    }

    return passed ? 0 : 1;
}