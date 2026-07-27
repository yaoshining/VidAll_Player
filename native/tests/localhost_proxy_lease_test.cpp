#include <iostream>

#include "proxy_lease_manager.h"

namespace {

bool check(bool condition, const char* message)
{
    if (!condition) {
        std::cerr << "FAILED: " << message << '\n';
        return false;
    }
    return true;
}

} // namespace

int main()
{
    vidall::ProxyLeaseManager leases;
    bool passed = true;

    const auto acquired = leases.acquire("lease-a", "http://127.0.0.1:58080/smb/a.mp4", 7);
    passed &= check(acquired.state == vidall::ProxyLeaseState::Acquired, "valid loopback lease is acquired");
    passed &= check(acquired.epoch == 7, "acquired lease retains epoch");
    passed &= check(leases.activeCount() == 1, "acquired lease is active");
    passed &= check(leases.acceptsByteRange("lease-a", 7), "current lease accepts Range requests");
    passed &= check(!leases.acceptsByteRange("lease-a", 6), "stale epoch rejects Range requests");
    const auto staleAcquire = leases.acquire("lease-a", "http://127.0.0.1:58080/smb/a.mp4", 6);
    passed &= check(staleAcquire.epoch == 7 && staleAcquire.state == vidall::ProxyLeaseState::Acquired,
        "stale acquire preserves the current lease epoch and state");
    passed &= check(leases.acceptsByteRange("lease-a", 7), "stale acquire cannot replace the current lease");

    const auto renewed = leases.renew("lease-a", 7);
    passed &= check(renewed.state == vidall::ProxyLeaseState::Renewed, "active lease can renew");
    const auto releaseRequest = leases.requestRelease("lease-a", 7, "source-switch");
    passed &= check(releaseRequest.state == vidall::ProxyLeaseState::ReleaseRequested,
        "source switch requests release before confirmation");
    passed &= check(leases.activeCount() == 1, "release request remains active until confirmation");
    passed &= check(!leases.acceptsByteRange("lease-a", 7), "release request blocks further Range requests");
    passed &= check(leases.requestRelease("lease-a", 7, "release").state == vidall::ProxyLeaseState::ReleaseRequested,
        "duplicate release request is idempotent");
    passed &= check(leases.confirmReleased("lease-a", 6).state == vidall::ProxyLeaseState::ReleaseRequested,
        "stale release confirmation is ignored");
    passed &= check(leases.confirmReleased("lease-a", 7).state == vidall::ProxyLeaseState::Released,
        "current release confirmation completes cleanup");
    passed &= check(leases.activeCount() == 0, "confirmed lease is inactive");

    const auto invalid = leases.acquire("lease-invalid", "http://example.com:58080/smb/a.mp4", 1);
    passed &= check(invalid.state == vidall::ProxyLeaseState::CleanupFailed,
        "non-loopback proxy URI fails deterministic cleanup");
    passed &= check(!invalid.retryable, "invalid proxy URI is not retryable");
    passed &= check(leases.acquire("lease-userinfo", "http://localhost@evil.test/smb/a.mp4", 1).state ==
            vidall::ProxyLeaseState::CleanupFailed,
        "proxy URI with user information is rejected");
    passed &= check(leases.acquire("lease-prefix", "http://127.0.0.10:58080/smb/a.mp4", 1).state ==
            vidall::ProxyLeaseState::CleanupFailed,
        "loopback-looking host prefix is rejected");
    passed &= check(leases.acquire("lease-ipv6", "http://[::1]:58080/smb/a.mp4", 1).state ==
            vidall::ProxyLeaseState::Acquired,
        "IPv6 loopback proxy is accepted");
    passed &= check(leases.acquire("lease-case", "HTTP://LOCALHOST:58080/smb/a.mp4", 1).state ==
            vidall::ProxyLeaseState::Acquired,
        "mixed-case loopback HTTP URI is accepted");
    passed &= check(leases.acquire("lease-port", "http://localhost:/smb/a.mp4", 1).state ==
            vidall::ProxyLeaseState::CleanupFailed,
        "loopback proxy URI with an empty port is rejected");

    leases.acquire("lease-expired", "http://localhost:58080/smb/b.mp4", 2);
    passed &= check(leases.expire("lease-expired", 2).state == vidall::ProxyLeaseState::Expired,
        "release timeout expires current lease");
    passed &= check(leases.cleanupFailed("lease-expired", 2).state == vidall::ProxyLeaseState::CleanupFailed,
        "cleanup failure is recorded after timeout");
    passed &= check(leases.cleanupFailed("lease-expired", 1).state == vidall::ProxyLeaseState::CleanupFailed,
        "stale cleanup callback cannot overwrite terminal state");

    return passed ? 0 : 1;
}
