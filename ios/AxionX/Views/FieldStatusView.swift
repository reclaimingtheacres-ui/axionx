import SwiftUI

// MARK: - Field Status Control
//
// Compact 3-segment pill shown on LPR pages so agents can set their
// availability without leaving the screen.
// Tapping a segment drives FieldStatusManager which controls location tracking.

struct FieldStatusView: View {

    @ObservedObject private var manager = FieldStatusManager.shared

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(FieldStatus.allCases.enumerated()), id: \.element.rawValue) { idx, status in
                statusButton(status)
                if idx < FieldStatus.allCases.count - 1 {
                    Rectangle()
                        .fill(Color(white: 0.82))
                        .frame(width: 0.5)
                        .padding(.vertical, 6)
                }
            }
        }
        .background(.regularMaterial)
        .clipShape(Capsule())
        .overlay(Capsule().stroke(Color(white: 0.85), lineWidth: 0.5))
        .shadow(color: .black.opacity(0.12), radius: 5, x: 0, y: 2)
    }

    @ViewBuilder
    private func statusButton(_ status: FieldStatus) -> some View {
        let isActive = manager.fieldStatus == status
        Button(action: { manager.setStatus(status) }) {
            HStack(spacing: 4) {
                Image(systemName: status.sfSymbol)
                    .font(.system(size: 11, weight: .semibold))
                Text(status.label)
                    .font(.system(size: 11, weight: .semibold))
            }
            .foregroundStyle(isActive ? .white : dotColor(status))
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(
                isActive
                    ? dotColor(status)
                    : Color.clear
            )
            .clipShape(Capsule())
        }
        .buttonStyle(.plain)
        .animation(.easeInOut(duration: 0.15), value: manager.fieldStatus)
    }

    private func dotColor(_ status: FieldStatus) -> Color {
        switch status {
        case .offDuty:   return Color(red: 0.42, green: 0.45, blue: 0.50)
        case .available: return Color(red: 0.09, green: 0.63, blue: 0.29)
        case .activeJob: return Color(red: 0.15, green: 0.50, blue: 0.95)
        }
    }
}

#Preview {
    FieldStatusView()
        .padding()
        .background(Color.gray.opacity(0.1))
}
