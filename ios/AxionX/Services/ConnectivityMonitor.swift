import Network
import Combine

/// Monitors network reachability using Apple's Network framework.
/// Exposed as an ObservableObject so SwiftUI views can react to connectivity changes.
final class ConnectivityMonitor: ObservableObject {

    /// True when any network path is available (WiFi, cellular, etc).
    @Published private(set) var isConnected: Bool = true

    private let monitor = NWPathMonitor()
    private let queue   = DispatchQueue(label: "com.axionx.connectivity", qos: .utility)

    init() {
        monitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                self?.isConnected = path.status == .satisfied
            }
        }
        monitor.start(queue: queue)
    }

    deinit {
        monitor.cancel()
    }
}
