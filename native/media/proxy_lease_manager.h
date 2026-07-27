#ifndef VIDALL_PROXY_LEASE_MANAGER_H
#define VIDALL_PROXY_LEASE_MANAGER_H

#include <cstdint>
#include <string>
#include <unordered_map>

namespace vidall {

enum class ProxyLeaseState {
    Acquired,
    Renewed,
    ReleaseRequested,
    Released,
    Expired,
    CleanupFailed,
};

struct ProxyLeaseStatus {
    std::string leaseId;
    ProxyLeaseState state;
    std::uint64_t epoch;
    bool retryable;
};

class ProxyLeaseManager {
public:
    ProxyLeaseStatus acquire(const std::string& leaseId, const std::string& uri, std::uint64_t epoch);
    ProxyLeaseStatus renew(const std::string& leaseId, std::uint64_t epoch);
    ProxyLeaseStatus requestRelease(const std::string& leaseId, std::uint64_t epoch, const std::string& reason);
    ProxyLeaseStatus confirmReleased(const std::string& leaseId, std::uint64_t epoch);
    ProxyLeaseStatus expire(const std::string& leaseId, std::uint64_t epoch);
    ProxyLeaseStatus cleanupFailed(const std::string& leaseId, std::uint64_t epoch);
    bool acceptsByteRange(const std::string& leaseId, std::uint64_t epoch) const;
    std::size_t activeCount() const;

private:
    struct LeaseRecord {
        std::uint64_t epoch;
        ProxyLeaseState state;
        bool retryable;
    };

    static bool isLoopbackHttpUri(const std::string& uri);
    static bool isActive(ProxyLeaseState state);
    ProxyLeaseStatus currentOrMissing(const std::string& leaseId) const;
    ProxyLeaseStatus transition(const std::string& leaseId, std::uint64_t epoch,
        ProxyLeaseState state, bool retryable, bool requireReleaseRequest);

    std::unordered_map<std::string, LeaseRecord> leases_;
};

} // namespace vidall
#endif
