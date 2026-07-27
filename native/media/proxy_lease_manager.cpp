#include "proxy_lease_manager.h"

#include <algorithm>
#include <cctype>

namespace {

std::string toLowerAscii(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char character) {
        return static_cast<char>(std::tolower(character));
    });
    return value;
}

bool isDecimalPort(const std::string& port)
{
    return !port.empty() && std::all_of(port.begin(), port.end(), [](unsigned char character) {
        return std::isdigit(character) != 0;
    });
}

} // namespace

namespace vidall {

ProxyLeaseStatus ProxyLeaseManager::acquire(const std::string& leaseId, const std::string& uri, std::uint64_t epoch)
{
    if (leaseId.empty() || epoch == 0 || !isLoopbackHttpUri(uri)) {
        return { leaseId, ProxyLeaseState::CleanupFailed, epoch, false };
    }
    const auto found = leases_.find(leaseId);
    if (found != leases_.end() && epoch <= found->second.epoch) {
        return currentOrMissing(leaseId);
    }
    leases_[leaseId] = { epoch, ProxyLeaseState::Acquired, true };
    return { leaseId, ProxyLeaseState::Acquired, epoch, true };
}

ProxyLeaseStatus ProxyLeaseManager::renew(const std::string& leaseId, std::uint64_t epoch)
{
    const auto found = leases_.find(leaseId);
    if (found == leases_.end() || found->second.epoch != epoch || !isActive(found->second.state)) {
        return currentOrMissing(leaseId);
    }
    found->second.state = ProxyLeaseState::Renewed;
    return { leaseId, ProxyLeaseState::Renewed, epoch, true };
}

ProxyLeaseStatus ProxyLeaseManager::requestRelease(const std::string& leaseId, std::uint64_t epoch, const std::string&)
{
    const auto found = leases_.find(leaseId);
    if (found == leases_.end() || found->second.epoch != epoch) {
        return currentOrMissing(leaseId);
    }
    if (found->second.state == ProxyLeaseState::ReleaseRequested) {
        return { leaseId, ProxyLeaseState::ReleaseRequested, epoch, true };
    }
    if (!isActive(found->second.state)) {
        return currentOrMissing(leaseId);
    }
    found->second.state = ProxyLeaseState::ReleaseRequested;
    return { leaseId, ProxyLeaseState::ReleaseRequested, epoch, true };
}

ProxyLeaseStatus ProxyLeaseManager::confirmReleased(const std::string& leaseId, std::uint64_t epoch)
{
    return transition(leaseId, epoch, ProxyLeaseState::Released, false, true);
}

ProxyLeaseStatus ProxyLeaseManager::expire(const std::string& leaseId, std::uint64_t epoch)
{
    return transition(leaseId, epoch, ProxyLeaseState::Expired, true, false);
}

ProxyLeaseStatus ProxyLeaseManager::cleanupFailed(const std::string& leaseId, std::uint64_t epoch)
{
    return transition(leaseId, epoch, ProxyLeaseState::CleanupFailed, true, false);
}

bool ProxyLeaseManager::acceptsByteRange(const std::string& leaseId, std::uint64_t epoch) const
{
    const auto found = leases_.find(leaseId);
    return found != leases_.end() && found->second.epoch == epoch && isActive(found->second.state);
}

std::size_t ProxyLeaseManager::activeCount() const
{
    std::size_t count = 0;
    for (const auto& item : leases_) {
        if (isActive(item.second.state) || item.second.state == ProxyLeaseState::ReleaseRequested) {
            ++count;
        }
    }
    return count;
}

bool ProxyLeaseManager::isLoopbackHttpUri(const std::string& uri)
{
    const std::string normalizedUri = toLowerAscii(uri);
    const std::string prefix = "http://";
    if (normalizedUri.rfind(prefix, 0) != 0) {
        return false;
    }
    const std::string authorityAndPath = normalizedUri.substr(prefix.size());
    const std::size_t authorityEnd = authorityAndPath.find_first_of("/?#");
    const std::string authority = authorityAndPath.substr(0, authorityEnd);
    if (authority.empty() || authority.find('@') != std::string::npos) {
        return false;
    }

    std::string host;
    std::string port;
    if (authority.front() == '[') {
        const std::size_t bracketEnd = authority.find(']');
        if (bracketEnd == std::string::npos) {
            return false;
        }
        host = authority.substr(0, bracketEnd + 1);
        if (bracketEnd + 1 < authority.size()) {
            if (authority[bracketEnd + 1] != ':') {
                return false;
            }
            port = authority.substr(bracketEnd + 2);
        }
    } else {
        const std::size_t portSeparator = authority.rfind(':');
        host = portSeparator == std::string::npos ? authority : authority.substr(0, portSeparator);
        if (portSeparator != std::string::npos) {
            port = authority.substr(portSeparator + 1);
        }
    }
    if (!port.empty() && !isDecimalPort(port)) {
        return false;
    }
    if (!authority.empty() && authority.back() == ':') {
        return false;
    }
    return host == "127.0.0.1" || host == "localhost" || host == "[::1]";
}

bool ProxyLeaseManager::isActive(ProxyLeaseState state)
{
    return state == ProxyLeaseState::Acquired || state == ProxyLeaseState::Renewed;
}

ProxyLeaseStatus ProxyLeaseManager::currentOrMissing(const std::string& leaseId) const
{
    const auto found = leases_.find(leaseId);
    if (found == leases_.end()) {
        return { leaseId, ProxyLeaseState::CleanupFailed, 0, false };
    }
    return { leaseId, found->second.state, found->second.epoch, found->second.retryable };
}

ProxyLeaseStatus ProxyLeaseManager::transition(const std::string& leaseId, std::uint64_t epoch,
    ProxyLeaseState state, bool retryable, bool requireReleaseRequest)
{
    const auto found = leases_.find(leaseId);
    if (found == leases_.end() || found->second.epoch != epoch ||
        (requireReleaseRequest && found->second.state != ProxyLeaseState::ReleaseRequested)) {
        return currentOrMissing(leaseId);
    }
    if (found->second.state == ProxyLeaseState::Released || found->second.state == ProxyLeaseState::CleanupFailed) {
        return currentOrMissing(leaseId);
    }
    found->second.state = state;
    found->second.retryable = retryable;
    return { leaseId, state, epoch, retryable };
}

} // namespace vidall
