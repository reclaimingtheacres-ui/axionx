import CoreLocation
import MapKit
import SwiftUI

// MARK: - Dispatch Sheet
//
// Native bottom sheet presented when an agent has an active LPR follow-up assigned.
// Shows: action type, priority, plate registration, ETA from current location.
// Provides one-tap status updates (En Route → Arrived → Complete) and
// deep-links to Apple Maps for turn-by-turn navigation.
//
// No customer name, address, arrears, or file data is displayed here.

struct DispatchSheet: View {

    let dispatch: DispatchSummary

    @ObservedObject private var manager = DispatchManager.shared
    @StateObject private var eta = ETAViewModel()

    var body: some View {
        VStack(spacing: 0) {
            dragHandle

            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    headerRow
                    sightingRow
                    etaRow
                    if dispatch.officeNote.isEmpty == false {
                        noteRow
                    }
                    Divider()
                    actionButtons
                }
                .padding(.horizontal, 20)
                .padding(.top, 12)
                .padding(.bottom, 32)
            }
        }
        .background(Color(UIColor.systemBackground))
        .task {
            if let loc = dispatch.location {
                await eta.fetch(to: loc)
            }
        }
    }

    // MARK: - Sub-views

    private var dragHandle: some View {
        RoundedRectangle(cornerRadius: 2.5)
            .fill(Color(white: 0.80))
            .frame(width: 36, height: 5)
            .padding(.top, 10)
            .padding(.bottom, 4)
            .frame(maxWidth: .infinity)
    }

    private var headerRow: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("LPR Follow-up")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(.secondary)
                Text(dispatch.actionLabel)
                    .font(.system(size: 20, weight: .bold))
                statusBadge
            }
            Spacer()
            priorityBadge
        }
    }

    private var statusBadge: some View {
        let label: String
        switch dispatch.status {
        case "assigned":    label = "Assigned"
        case "en_route":    label = "En Route"
        case "near_target": label = "Near Target"
        case "arrived":     label = "Arrived"
        default:            label = dispatch.status.capitalized
        }
        return Text(label)
            .font(.system(size: 11, weight: .semibold))
            .padding(.horizontal, 9)
            .padding(.vertical, 3)
            .background(Color(white: 0.93))
            .clipShape(Capsule())
    }

    private var priorityBadge: some View {
        let c = dispatch.priorityColor
        return Text(dispatch.priority.capitalized)
            .font(.system(size: 12, weight: .bold))
            .foregroundColor(.white)
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(Color(red: c.red, green: c.green, blue: c.blue))
            .clipShape(Capsule())
    }

    private var sightingRow: some View {
        VStack(alignment: .leading, spacing: 4) {
            Label("Plate", systemImage: "car.rear.fill")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.secondary)
            Text(dispatch.sighting.registration.isEmpty
                 ? "Unknown" : dispatch.sighting.registration)
                .font(.system(size: 17, weight: .semibold, design: .monospaced))
            if !dispatch.sighting.sightingAt.isEmpty {
                Text("Sighted \(dispatch.sighting.sightingAt.prefix(16))")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(UIColor.secondarySystemBackground))
        .cornerRadius(12)
    }

    private var etaRow: some View {
        HStack(spacing: 12) {
            Image(systemName: "location.fill")
                .foregroundColor(Color(red: 0.15, green: 0.50, blue: 0.95))
                .font(.system(size: 16))
            VStack(alignment: .leading, spacing: 2) {
                if let etaText = eta.etaLabel {
                    Text(etaText)
                        .font(.system(size: 16, weight: .semibold))
                    if let dist = eta.distLabel {
                        Text(dist).font(.system(size: 12)).foregroundStyle(.secondary)
                    }
                } else if eta.isFetching {
                    ProgressView().scaleEffect(0.7)
                } else {
                    Text("ETA unavailable")
                        .font(.system(size: 14))
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            if dispatch.location != nil {
                Button(action: { manager.openInMaps() }) {
                    Label("Navigate", systemImage: "map.fill")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 7)
                        .background(Color(red: 0.15, green: 0.50, blue: 0.95))
                        .cornerRadius(10)
                }
            }
        }
        .padding(14)
        .background(Color(UIColor.secondarySystemBackground))
        .cornerRadius(12)
    }

    private var noteRow: some View {
        VStack(alignment: .leading, spacing: 4) {
            Label("Office Note", systemImage: "note.text")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.secondary)
            Text(dispatch.officeNote)
                .font(.system(size: 14))
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(UIColor.secondarySystemBackground))
        .cornerRadius(12)
    }

    private var actionButtons: some View {
        VStack(spacing: 10) {
            switch dispatch.status {
            case "assigned":
                primaryButton("En Route", icon: "car.fill",
                              color: Color(red: 0.15, green: 0.50, blue: 0.95)) {
                    manager.updateStatus("en_route")
                    manager.openInMaps()
                }
            case "en_route", "near_target":
                primaryButton("Mark Arrived", icon: "mappin.circle.fill",
                              color: Color(red: 0.09, green: 0.63, blue: 0.29)) {
                    manager.updateStatus("arrived")
                }
                if dispatch.location != nil {
                    secondaryButton("Navigate Again", icon: "map") {
                        manager.openInMaps()
                    }
                }
            case "arrived":
                primaryButton("Complete", icon: "checkmark.circle.fill",
                              color: Color(red: 0.09, green: 0.63, blue: 0.29)) {
                    manager.updateStatus("completed")
                }
            default:
                EmptyView()
            }

            Button(action: { manager.dismissDispatch() }) {
                Text("Dismiss")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
            }
        }
    }

    @ViewBuilder
    private func primaryButton(_ label: String, icon: String,
                                color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Label(label, systemImage: icon)
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(color)
                .cornerRadius(13)
        }
    }

    @ViewBuilder
    private func secondaryButton(_ label: String, icon: String,
                                  action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Label(label, systemImage: icon)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(Color(red: 0.15, green: 0.50, blue: 0.95))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(Color(red: 0.15, green: 0.50, blue: 0.95).opacity(0.10))
                .cornerRadius(13)
        }
    }
}

// MARK: - ETA view model (MapKit MKDirections)

@MainActor
final class ETAViewModel: ObservableObject {
    @Published var etaLabel:  String? = nil
    @Published var distLabel: String? = nil
    @Published var isFetching = false

    func fetch(to destination: CLLocation) async {
        guard !isFetching else { return }
        isFetching = true
        defer { isFetching = false }

        let destPlacemark = MKPlacemark(coordinate: destination.coordinate)
        let destItem      = MKMapItem(placemark: destPlacemark)

        let request = MKDirections.Request()
        request.source          = .forCurrentLocation()
        request.destination     = destItem
        request.transportType   = .automobile
        request.requestsAlternateRoutes = false

        do {
            let directions = MKDirections(request: request)
            let response   = try await directions.calculate()
            if let route = response.routes.first {
                let mins = Int(route.expectedTravelTime / 60)
                etaLabel  = mins < 2 ? "< 2 min ETA"
                          : mins < 60 ? "~\(mins) min ETA"
                          : "~\(mins / 60)h \(mins % 60)m ETA"
                let km = route.distance / 1000
                distLabel = km < 1
                    ? "\(Int(route.distance)) m away"
                    : String(format: "%.1f km away", km)
            }
        } catch {
            // MKDirections can fail if location permission is unavailable or no network
            etaLabel = nil
        }
    }
}

#Preview {
    DispatchSheet(dispatch: DispatchSummary(
        id: 42,
        actionType: "field_locate",
        priority: "high",
        status: "assigned",
        dueAt: "",
        officeNote: "Check the industrial estate entrance.",
        sighting: DispatchSummary.SightingLocation(
            id: 7,
            registration: "ABC123",
            resultType: "allocated_match",
            latitude: -33.865, longitude: 151.209,
            sightingAt: "2026-03-06 14:22"
        )
    ))
}
