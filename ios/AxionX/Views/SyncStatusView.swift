import SwiftUI

// MARK: - Sync Status Sheet
//
// Shows pending uploads, failed actions with per-item retry, and a recent
// success list.  Accessible via the orange pill badge that appears in the
// WebViewContainer when there are unsynced items.

struct SyncStatusView: View {

    @EnvironmentObject private var syncManager: SyncManager
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            List {
                summarySection
                if !syncManager.pendingItems.isEmpty { pendingSection }
                if !syncManager.failedItems.isEmpty  { failedSection  }
                if !syncManager.recentItems.isEmpty  { recentSection  }
                if  syncManager.pendingItems.isEmpty
                 && syncManager.failedItems.isEmpty
                 && syncManager.recentItems.isEmpty  { emptySection   }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Sync Status")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Close") { dismiss() }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    syncNowButton
                }
            }
        }
        .presentationDetents([.medium, .large])
        .onAppear { syncManager.refreshCounts() }
    }

    // MARK: - Summary

    private var summarySection: some View {
        Section {
            HStack(spacing: 16) {
                counterCell(
                    value:  syncManager.pendingCount,
                    label:  "Pending",
                    color:  .orange
                )
                Divider().frame(height: 36)
                counterCell(
                    value:  syncManager.failedCount,
                    label:  "Failed",
                    color:  .red
                )
                Divider().frame(height: 36)
                counterCell(
                    value:  syncManager.assignedFollowupCount,
                    label:  "Follow-ups",
                    color:  .purple
                )
            }
            .padding(.vertical, 6)

            if let last = syncManager.lastSyncAt {
                Label("Last synced \(last.formatted(.relative(presentation: .named)))",
                      systemImage: "checkmark.circle")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                Label("Not yet synced this session",
                      systemImage: "clock")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }

    private func counterCell(value: Int, label: String, color: Color) -> some View {
        VStack(spacing: 2) {
            Text("\(value)")
                .font(.system(size: 24, weight: .bold, design: .rounded))
                .foregroundColor(value > 0 ? color : .secondary)
            Text(label)
                .font(.system(size: 11, weight: .medium))
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Pending section

    private var pendingSection: some View {
        Section("Pending Upload") {
            ForEach(syncManager.pendingItems) { item in
                queueRow(item: item, showRetry: false)
            }
        }
    }

    // MARK: - Failed section

    private var failedSection: some View {
        Section {
            ForEach(syncManager.failedItems) { item in
                queueRow(item: item, showRetry: true)
            }
        } header: {
            HStack {
                Text("Failed")
                Spacer()
                Button("Retry All") {
                    Task { await syncManager.retryFailed() }
                }
                .font(.caption)
                .foregroundColor(.accentColor)
            }
        }
    }

    // MARK: - Recent successes

    private var recentSection: some View {
        Section("Recently Synced") {
            ForEach(syncManager.recentItems) { item in
                queueRow(item: item, showRetry: false)
            }
        }
    }

    // MARK: - Empty state

    private var emptySection: some View {
        Section {
            HStack {
                Spacer()
                VStack(spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 36))
                        .foregroundColor(.green)
                    Text("All actions synced")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.vertical, 20)
                Spacer()
            }
        }
    }

    // MARK: - Row

    private func queueRow(item: OfflineQueueItem, showRetry: Bool) -> some View {
        HStack(alignment: .center, spacing: 10) {
            statusIcon(for: item.status)
                .font(.system(size: 16))
                .frame(width: 22)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(item.actionLabel)
                        .font(.system(size: 14, weight: .medium))
                    if let plate = item.plateLabel, !plate.isEmpty {
                        Text(plate)
                            .font(.system(size: 13, weight: .bold, design: .monospaced))
                            .foregroundColor(.secondary)
                    }
                }
                if let err = item.lastError, item.status == .failed {
                    Text(err)
                        .font(.caption)
                        .foregroundColor(.red)
                }
                Text(item.createdAt.formatted(date: .omitted, time: .shortened)
                     + " · \(item.createdAt.formatted(.dateTime.day().month(.abbreviated)))"
                     + (item.retryCount > 0 ? " · \(item.retryCount) retr\(item.retryCount == 1 ? "y" : "ies")" : ""))
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            }

            Spacer()

            if showRetry {
                Button("Retry") {
                    Task { await syncManager.retryFailed() }
                }
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(.accentColor)
            }
        }
        .padding(.vertical, 2)
    }

    private func statusIcon(for status: QueueItemStatus) -> some View {
        Group {
            switch status {
            case .pending:  Image(systemName: "clock").foregroundColor(.orange)
            case .syncing:  Image(systemName: "arrow.triangle.2.circlepath").foregroundColor(.blue)
            case .success:  Image(systemName: "checkmark.circle.fill").foregroundColor(.green)
            case .failed:   Image(systemName: "exclamationmark.circle.fill").foregroundColor(.red)
            }
        }
    }

    // MARK: - Sync Now button

    private var syncNowButton: some View {
        Button(action: { Task { await syncManager.syncNow() } }) {
            if syncManager.isSyncing {
                ProgressView().scaleEffect(0.8)
            } else {
                Label("Sync", systemImage: "arrow.triangle.2.circlepath")
                    .font(.system(size: 14, weight: .semibold))
            }
        }
        .disabled(syncManager.isSyncing)
    }
}
