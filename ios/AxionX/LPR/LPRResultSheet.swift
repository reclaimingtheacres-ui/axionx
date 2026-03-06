import SwiftUI
import WebKit

// MARK: - Data model (only safe / non-restricted fields)

struct LPRResult {
    let resultType:          String
    let searchedReg:         String
    let searchMethod:        String
    let matchedJobId:        Int?
    let matchedJobNumber:    String?
    let openURL:             String?
    let assetRegistration:   String?
    let assetYear:           String?
    let assetMake:           String?
    let assetModel:          String?
    let matchCount:          Int?
    let message:             String?
    // Watchlist
    let watchlistHit:        Bool
    let watchlistReason:     String?
    let watchlistPriority:   String?

    init(from json: [String: Any], searchMethod: String) {
        self.resultType        = json["result_type"]           as? String ?? "invalid"
        self.searchedReg       = json["searched_registration"] as? String ?? ""
        self.searchMethod      = searchMethod
        self.matchedJobId      = json["matched_job_id"]        as? Int
        self.matchedJobNumber  = json["matched_job_number"]    as? String
        self.openURL           = json["open_url"]              as? String
        self.matchCount        = json["match_count"]           as? Int
        self.message           = json["message"]               as? String
        self.watchlistHit      = json["watchlist_hit"]         as? Bool ?? false
        self.watchlistReason   = json["watchlist_reason"]      as? String
        self.watchlistPriority = json["watchlist_priority"]    as? String
        if let asset = json["asset"] as? [String: Any] {
            self.assetRegistration = asset["registration"] as? String
            self.assetYear         = asset["year"]         as? String
            self.assetMake         = asset["make"]         as? String
            self.assetModel        = asset["model"]        as? String
        } else {
            self.assetRegistration = nil
            self.assetYear = nil; self.assetMake = nil; self.assetModel = nil
        }
    }

    var vehicleLabel: String {
        [assetYear, assetMake, assetModel].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " ")
    }

    var displayRegistration: String { assetRegistration ?? searchedReg }

    var canSaveSighting: Bool {
        ["restricted_match", "conflict", "no_match"].contains(resultType)
    }
}

// MARK: - API client (shares WKWebView session cookies)

enum LPRAPIClient {

    static func lookup(plate: String, method: String, webView: WKWebView,
                       completion: @escaping (LPRResult?) -> Void) {
        request(path: "/m/api/lpr/lookup",
                body: ["registration": plate, "method": method],
                webView: webView) { json in
            guard let json = json else { completion(nil); return }
            completion(LPRResult(from: json, searchMethod: method))
        }
    }

    static func saveSighting(_ body: [String: Any], webView: WKWebView,
                             completion: @escaping (Bool, Int?) -> Void) {
        request(path: "/m/api/lpr/sighting", body: body, webView: webView) { json in
            let ok = json?["ok"] as? Bool ?? false
            let id = json?["sighting_id"] as? Int
            completion(ok, id)
        }
    }

    private static func request(path: String, body: [String: Any],
                                 webView: WKWebView,
                                 completion: @escaping ([String: Any]?) -> Void) {
        webView.configuration.websiteDataStore.httpCookieStore.getAllCookies { cookies in
            guard let base = AppConfig.entryURL.host else { completion(nil); return }
            var comps      = URLComponents()
            comps.scheme   = AppConfig.entryURL.scheme
            comps.host     = base
            comps.path     = path
            guard let url  = comps.url else { completion(nil); return }

            var req            = URLRequest(url: url)
            req.httpMethod     = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.setValue("AxionXiOS/1.0",    forHTTPHeaderField: "User-Agent")
            req.httpBody       = try? JSONSerialization.data(withJSONObject: body)

            let cookieHeader = cookies
                .filter { $0.domain.hasSuffix(base) || base.hasSuffix($0.domain.hasPrefix(".") ? String($0.domain.dropFirst()) : $0.domain) }
                .map    { "\($0.name)=\($0.value)" }
                .joined(separator: "; ")
            if !cookieHeader.isEmpty {
                req.setValue(cookieHeader, forHTTPHeaderField: "Cookie")
            }

            URLSession.shared.dataTask(with: req) { data, _, _ in
                let json = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
                DispatchQueue.main.async { completion(json) }
            }.resume()
        }
    }
}

// MARK: - Native result sheet

struct LPRResultSheet: View {
    let result:  LPRResult
    let webView: WKWebView
    var onOpenJob:  (String) -> Void
    var onDismiss:  () -> Void

    @State private var notes: String = ""
    @State private var escalate  = false
    @State private var isSaving  = false
    @State private var savedOK   = false
    @State private var saveError: String? = nil
    @State private var gpsLabel  = "Fetching location…"
    @State private var latitude:  Double? = nil
    @State private var longitude: Double? = nil

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {

                    // Watchlist alert — shown above all other content
                    if result.watchlistHit {
                        watchlistAlert
                            .padding(.bottom, 14)
                    }

                    resultBanner
                        .padding(.bottom, 16)

                    plateCard
                        .padding(.bottom, 12)

                    if result.resultType == "allocated_match" {
                        allocatedActions
                    } else if result.canSaveSighting {
                        sightingForm
                    }

                    Spacer(minLength: 32)
                }
                .padding(20)
            }
            .navigationTitle("Plate Result")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Close") { onDismiss() }
                }
            }
        }
        .onAppear { fetchGPS() }
    }

    // MARK: Watchlist alert

    private var watchlistAlert: some View {
        let isUrgent = result.watchlistPriority == "urgent"
        let isHigh   = result.watchlistPriority == "high"
        let bg    = isUrgent ? Color.red.opacity(0.1)    : Color.purple.opacity(0.1)
        let brd   = isUrgent ? Color.red.opacity(0.5)    : Color(red: 0.55, green: 0.2, blue: 0.9).opacity(0.5)
        let fg    = isUrgent ? Color.red                 : Color(red: 0.49, green: 0.14, blue: 0.82)

        return HStack(alignment: .top, spacing: 12) {
            Text("⚑")
                .font(.system(size: 22))
            VStack(alignment: .leading, spacing: 4) {
                Text("WATCHLIST HIT")
                    .font(.system(size: 12, weight: .black))
                    .foregroundColor(fg)
                    .tracking(1)
                if isUrgent {
                    Text("URGENT — Contact the office immediately")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundColor(.red)
                } else if isHigh {
                    Text("HIGH PRIORITY")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundColor(.orange)
                }
                if let reason = result.watchlistReason, !reason.isEmpty {
                    Text(reason)
                        .font(.system(size: 13))
                        .foregroundColor(fg.opacity(0.85))
                }
            }
        }
        .padding(14)
        .background(bg)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(brd, lineWidth: isUrgent ? 2 : 1.5))
        .cornerRadius(12)
    }

    // MARK: Result banner

    private var resultBanner: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: bannerIcon)
                .font(.system(size: 22))
                .foregroundColor(bannerForeground)
                .padding(.top, 1)
            VStack(alignment: .leading, spacing: 4) {
                Text(bannerTitle)
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(bannerForeground)
                    .textCase(.uppercase)
                    .tracking(0.8)
                Text(bannerBody)
                    .font(.system(size: 14))
                    .foregroundColor(bannerForeground.opacity(0.85))
            }
        }
        .padding(14)
        .background(bannerBackground)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(bannerBorder, lineWidth: 1.5))
        .cornerRadius(12)
    }

    // MARK: Plate card

    private var plateCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(result.displayRegistration)
                .font(.system(size: 38, weight: .black, design: .monospaced))
                .tracking(4)
                .minimumScaleFactor(0.7)
                .lineLimit(1)

            if !result.vehicleLabel.isEmpty {
                HStack(spacing: 6) {
                    Image(systemName: "car.fill")
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                    Text(result.vehicleLabel)
                        .font(.system(size: 15, weight: .medium))
                        .foregroundColor(.secondary)
                }
            }

            if let jn = result.matchedJobNumber {
                HStack(spacing: 6) {
                    Image(systemName: "doc.text")
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                    Text("Job: \(jn)")
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                }
            }

            methodPill
        }
        .padding(16)
        .background(Color(.systemGray6))
        .cornerRadius(14)
    }

    private var methodPill: some View {
        let (icon, label, color): (String, String, Color) = {
            switch result.searchMethod {
            case "photo_ocr":  return ("camera", "Photo OCR", .blue)
            case "live_scan":  return ("viewfinder", "Live Scan", .purple)
            default:           return ("pencil", "Manual Entry", .secondary)
            }
        }()
        return Label(label, systemImage: icon)
            .font(.system(size: 12, weight: .semibold))
            .foregroundColor(color)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(color.opacity(0.1))
            .cornerRadius(8)
    }

    // MARK: Allocated actions

    private var allocatedActions: some View {
        VStack(spacing: 12) {
            if let urlStr = result.openURL {
                Button(action: { onOpenJob(urlStr) }) {
                    Label("Open Job File", systemImage: "doc.text.magnifyingglass")
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 15)
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                        .font(.system(size: 16, weight: .semibold))
                }
            }
            Button(action: onDismiss) {
                Text("Close")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 13)
                    .background(Color(.systemGray5))
                    .foregroundColor(.primary)
                    .cornerRadius(12)
            }
        }
    }

    // MARK: Sighting form

    private var sightingForm: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Save Sighting")
                .font(.system(size: 15, weight: .bold))
                .padding(.top, 4)

            HStack(spacing: 8) {
                Image(systemName: latitude != nil ? "location.fill" : "location.slash")
                    .font(.system(size: 14))
                    .foregroundColor(latitude != nil ? .green : .secondary)
                Text(gpsLabel)
                    .font(.system(size: 13))
                    .foregroundColor(.secondary)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Notes (optional)")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(.secondary)
                ZStack(alignment: .topLeading) {
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color(.systemGray6))
                        .frame(minHeight: 88)
                    if notes.isEmpty {
                        Text("Add an observation note…")
                            .font(.system(size: 15))
                            .foregroundColor(Color(.placeholderText))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 10)
                    }
                    TextEditor(text: $notes)
                        .font(.system(size: 15))
                        .frame(minHeight: 88)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 6)
                        .background(Color.clear)
                        .scrollContentBackground(.hidden)
                }
            }

            Toggle(isOn: $escalate) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Flag for office follow-up")
                        .font(.system(size: 15, weight: .medium))
                    Text("Adds this to the escalated sightings queue")
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                }
            }
            .toggleStyle(SwitchToggleStyle(tint: .orange))

            if savedOK {
                HStack(spacing: 10) {
                    Image(systemName: "checkmark.circle.fill").foregroundColor(.green)
                    Text("Sighting saved").font(.system(size: 15, weight: .semibold)).foregroundColor(.green)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 13)
                .background(Color.green.opacity(0.1))
                .cornerRadius(12)

                Button(action: onDismiss) {
                    Text("Close")
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 13)
                        .background(Color(.systemGray5))
                        .foregroundColor(.primary)
                        .cornerRadius(12)
                }
            } else {
                if let err = saveError {
                    Text(err).font(.system(size: 13)).foregroundColor(.red).padding(.vertical, 6)
                }

                Button(action: doSaveSighting) {
                    HStack(spacing: 8) {
                        if isSaving { ProgressView().tint(.white) }
                        else { Image(systemName: "mappin.and.ellipse") }
                        Text(isSaving ? "Saving…" : "Save Sighting").fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 15)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }
                .disabled(isSaving)

                Button(action: onDismiss) {
                    Text("Discard")
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 13)
                        .background(Color(.systemGray5))
                        .foregroundColor(.secondary)
                        .cornerRadius(12)
                }
            }
        }
    }

    // MARK: Save logic

    private func doSaveSighting() {
        isSaving  = true
        saveError = nil
        var body: [String: Any] = [
            "registration_raw":    result.searchedReg,
            "result_type":         result.resultType,
            "search_method":       result.searchMethod,
            "escalated_to_office": escalate,
            "watchlist_hit":       result.watchlistHit,
            "notes":               notes,
        ]
        if let jid = result.matchedJobId     { body["matched_job_id"]    = jid }
        if let jn  = result.matchedJobNumber { body["matched_job_number"] = jn  }
        if let lat = latitude  { body["latitude"]  = lat }
        if let lng = longitude { body["longitude"] = lng }

        LPRAPIClient.saveSighting(body, webView: webView) { ok, _ in
            isSaving = false
            if ok { savedOK = true }
            else  { saveError = "Save failed. Check your connection and try again." }
        }
    }

    private func fetchGPS() {
        LPRLocationService.shared.currentLocation { loc in
            if let loc = loc {
                latitude  = loc.coordinate.latitude
                longitude = loc.coordinate.longitude
                gpsLabel = String(format: "%.4f, %.4f",
                                  loc.coordinate.latitude, loc.coordinate.longitude)
            } else {
                gpsLabel = "Location unavailable"
            }
        }
    }

    // MARK: Theme helpers

    private var bannerIcon: String {
        switch result.resultType {
        case "allocated_match":  return "checkmark.circle.fill"
        case "restricted_match": return "exclamationmark.triangle.fill"
        case "conflict":         return "exclamationmark.octagon.fill"
        case "no_match":         return "magnifyingglass"
        default:                 return "xmark.circle"
        }
    }

    private var bannerTitle: String {
        switch result.resultType {
        case "allocated_match":  return "Match found"
        case "restricted_match": return "Not allocated to you"
        case "conflict":         return "Multiple active files"
        case "no_match":         return "No match"
        default:                 return "Invalid plate"
        }
    }

    private var bannerBody: String {
        if let msg = result.message { return msg }
        switch result.resultType {
        case "allocated_match":  return "This file is allocated to our agent."
        case "restricted_match": return "Contact the office for instructions."
        case "conflict":         return "Contact the office for instructions."
        case "no_match":         return "No active job found for this registration."
        default:                 return "Could not process this plate."
        }
    }

    private var bannerBackground: Color {
        switch result.resultType {
        case "allocated_match":  return Color.green.opacity(0.1)
        case "restricted_match": return Color.orange.opacity(0.1)
        case "conflict":         return Color.red.opacity(0.1)
        default:                 return Color(.systemGray6)
        }
    }

    private var bannerBorder: Color {
        switch result.resultType {
        case "allocated_match":  return Color.green.opacity(0.5)
        case "restricted_match": return Color.orange.opacity(0.45)
        case "conflict":         return Color.red.opacity(0.45)
        default:                 return Color(.systemGray4)
        }
    }

    private var bannerForeground: Color {
        switch result.resultType {
        case "allocated_match":  return Color(red: 0.08, green: 0.5, blue: 0.15)
        case "restricted_match": return Color(red: 0.65, green: 0.35, blue: 0)
        case "conflict":         return Color(red: 0.7, green: 0.1, blue: 0.1)
        default:                 return Color(.label)
        }
    }
}
