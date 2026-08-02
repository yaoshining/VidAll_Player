#ifndef VIDALL_CAPABILITY_REPORTER_H
#define VIDALL_CAPABILITY_REPORTER_H

#include <string>

namespace vidall {

enum class HardwareDecoding { Active, Fallback, Unavailable };

struct CapabilityObservation {
    std::string decoder;
    bool hardwareDecodingRequested = false;
    std::string container;
    std::string protocol;
};

struct CapabilityReport {
    std::string decoder;
    HardwareDecoding hardwareDecoding = HardwareDecoding::Unavailable;
    bool containerSupported = false;
    bool protocolSupported = false;
};

class CapabilityReporter {
public:
    static CapabilityReport report(const CapabilityObservation& observation);
};

} // namespace vidall
#endif
