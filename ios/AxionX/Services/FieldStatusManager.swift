import Foundation
import SwiftUI

// MARK: - Field Status enum

enum FieldStatus: String, Codable, CaseIterable {
    case offDuty   = "off_duty"
    case available = "available"
    case activeJob = "active_job"

    var label: String {
        switch self {
        case .offDuty:   return "Off Duty"
        case .available: return "Available"
        case .activeJob: return "Active Job"
        }
    }

    var sfSymbol: String {
        switch self {
        case .offDuty:   return "moon.fill"
        case .available: return "checkmark.circle.fill"
        case .activeJob: return "location.fill"
        }
    }

    /// Source string sent to the location-ping backend endpoint
    var locationSource: String {
        switch self {
        case .offDuty:   return "off_duty"
        case .available: return "background_significant_change"
        case .activeJob: return "active_job"
        }
    }
}

// MARK: - Field Status Manager

/// Singleton that owns field-status state, persists it, and drives AgentLocationService.
/// All mutations are on MainActor so @Published changes flow to SwiftUI synchronously.
@MainActor
final class FieldStatusManager: ObservableObject {

    static let shared = FieldStatusManager()

    @Published private(set) var fieldStatus: FieldStatus = .offDuty

    /// Non-nil while Active Job is running; shows time remaining
    @Published private(set) var activeJobExpiresAt: Date? = nil

    private let udKey = "com.axionx.field_status_v2"

    private init() {
        let raw    = UserDefaults.standard.string(forKey: udKey)
        let saved  = raw.flatMap { FieldStatus(rawValue: $0) } ?? .offDuty
        // Active Job never survives an app restart — downgrade to Available
        fieldStatus = (saved == .activeJob) ? .available : saved
        applyToLocationService()
    }

    // MARK: - Public interface

    func setStatus(_ status: FieldStatus) {
        guard fieldStatus != status else { return }
        fieldStatus = status
        UserDefaults.standard.set(status.rawValue, forKey: udKey)
        if status == .activeJob {
            activeJobExpiresAt = Date().addingTimeInterval(AgentLocationService.activeJobDuration)
        } else {
            activeJobExpiresAt = nil
        }
        applyToLocationService()
    }

    /// Called by AgentLocationService timer when activeJob duration expires
    func downgradeActiveJob() {
        if fieldStatus == .activeJob {
            setStatus(.available)
        }
    }

    // MARK: - Private

    private func applyToLocationService() {
        AgentLocationService.shared.apply(fieldStatus)
    }
}
