#include <iostream>
#include <string>

#include "CapabilityReporter.h"

namespace {
bool check(bool value, const char* message) { if (!value) { std::cerr << "FAILED: " << message << '\n'; } return value; }
}

int main()
{
    bool passed = true;
    const auto active = vidall::CapabilityReporter::report({"h264_videotoolbox", true, "mp4", "https"});
    passed &= check(active.decoder == "h264_videotoolbox", "reports selected decoder");
    passed &= check(active.hardwareDecoding == vidall::HardwareDecoding::Active, "reports active hardware decoder");
    passed &= check(active.containerSupported, "reports known container");
    passed &= check(active.protocolSupported, "reports known protocol");

    const auto fallback = vidall::CapabilityReporter::report({"h264", false, "unknown", "rtsp"});
    passed &= check(fallback.hardwareDecoding == vidall::HardwareDecoding::Fallback, "reports software fallback");
    passed &= check(!fallback.containerSupported && !fallback.protocolSupported, "does not infer unsupported capabilities");
    return passed ? 0 : 1;
}
