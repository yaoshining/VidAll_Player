#include <iostream>
#include <string>

#include "MediaParameters.h"

namespace {
bool check(bool value, const char* message) { if (!value) { std::cerr << "FAILED: " << message << '\n'; } return value; }
}

int main()
{
    bool passed = true;
    const auto video = vidall::MediaParameters::video({1920, 1080, "yuv420p", 90, 4, 3, "h264", true});
    passed &= check(video.width == 1920 && video.rotation == 90, "reports real video dimensions and rotation");
    passed &= check(video.pixelAspectRatio == "4:3", "reports pixel aspect ratio");
    passed &= check(video.colorBaseline == "sdr", "uses SDR unless a verified event says otherwise");
    const auto audio = vidall::MediaParameters::audio({48000, 2, "stereo", "aac"});
    passed &= check(audio.sampleRate == 48000 && audio.channels == 2, "reports audio parameters");
    passed &= check(vidall::MediaParameters::isUnsupported("crop"), "crop remains unsupported");
    passed &= check(!vidall::MediaParameters::isUnsupported("rotate"), "rotation is reported rather than blocked");
    return passed ? 0 : 1;
}
