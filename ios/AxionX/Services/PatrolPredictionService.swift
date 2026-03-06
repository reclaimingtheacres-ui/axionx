import CoreML
import Foundation
import WebKit

// MARK: - Patrol Prediction Service
//
// Loads a bundled Core ML tabular classifier (LPRPatrolModel.mlmodelc) and
// runs batch inference against the patrol API items.  Scores are posted back to
// the server so the admin and mobile pages can display combined (rule + ML)
// confidence.
//
// BUNDLING THE MODEL
// ──────────────────
// 1. Export training data: GET /admin/lpr/patrol/export.csv
// 2. Train in Create ML (macOS):
//    - Project type: Tabular Classifier
//    - Target column: seen_again_72h
//    - Feature columns: repeat_count_30d, distinct_agent_count, is_watchlist,
//        result_type_allocated, result_type_restricted, result_type_conflict,
//        day_bucket_weekday, day_bucket_weekend, day_bucket_both,
//        time_window_morning, time_window_afternoon, time_window_evening,
//        time_window_night, has_gps_cluster, rule_confidence_score
// 3. Export → "LPRPatrolModel.mlmodel", compile → "LPRPatrolModel.mlmodelc"
// 4. Drag "LPRPatrolModel.mlmodelc" into the Xcode project (add to target)
//
// Until the model is bundled, scoring is silently disabled and the rule-based
// score is used as the combined score on the server.
//
// RESCORING CADENCE
// ─────────────────
// runBatchScoringIfNeeded() is called from SyncManager after each remote-state
// refresh.  It respects a 6-hour minimum interval so it does not run on every
// sync.  Scoring is entirely opportunistic and never blocks the UI.
//
// DATA PRIVACY
// ────────────
// Only operational features are sent to the model (repeat counts, time patterns,
// zone presence, watchlist flag, result type).  No customer, finance, or
// personally-identifying data is used.

@MainActor
final class PatrolPredictionService {

    static let shared = PatrolPredictionService()

    // MARK: - State

    private var mlModel: MLModel?

    /// Populated once the model loads successfully.
    private(set) var modelVersion: String = "unscored"

    /// True when the compiled model file is present in the bundle and loaded.
    var modelAvailable: Bool { mlModel != nil }

    private var lastScoredAt: Date?

    /// Minimum time between automatic rescore passes (6 hours).
    private let minRescoringInterval: TimeInterval = 6 * 3600

    // MARK: - Init

    private init() { loadModel() }

    // MARK: - Model loading

    private func loadModel() {
        guard let url = Bundle.main.url(forResource: "LPRPatrolModel",
                                        withExtension: "mlmodelc") else {
            return  // model not yet bundled — scoring silently disabled
        }
        do {
            mlModel      = try MLModel(contentsOf: url)
            modelVersion = "v1.0"
        } catch {
            mlModel = nil
        }
    }

    // MARK: - Public API

    /// Called from SyncManager after each remote-state refresh.
    /// Runs only when the model is available and the cooldown has elapsed.
    func runBatchScoringIfNeeded(webView: WKWebView) {
        guard modelAvailable else { return }
        if let last = lastScoredAt,
           Date().timeIntervalSince(last) < minRescoringInterval { return }
        Task { await runBatchScoring(webView: webView) }
    }

    // MARK: - Batch scoring

    private func runBatchScoring(webView: WKWebView) async {
        guard let model = mlModel else { return }
        guard let items = await fetchPatrolItems(webView: webView),
              !items.isEmpty else { return }

        var scores: [[String: Any]] = []
        for item in items {
            guard let reg = item["registration"] as? String else { continue }
            if let prob = runInference(model: model, item: item) {
                scores.append([
                    "registration": reg,
                    "ml_score":     Int(prob * 100.0),
                ])
            }
        }

        guard !scores.isEmpty else { return }
        await uploadScores(scores: scores, webView: webView)
        lastScoredAt = Date()
    }

    // MARK: - Core ML inference

    /// Runs the model on one patrol item (raw dictionary from the JSON API).
    /// Returns a probability in 0.0–1.0, or nil on any error.
    func runInference(model: MLModel, item: [String: Any]) -> Double? {
        let repeatCount    = Double(item["repeat_count"]  as? Int ?? 0)
        let agentCount     = Double(item["agent_count"]   as? Int ?? 0)
        let isWatchlist    = Double((item["watchlist_hit"] as? Bool ?? false) ? 1 : 0)
        let resultType     = item["result_type"]  as? String ?? "no_match"
        let dayBucket      = item["day_bucket"]   as? String ?? "unknown"
        let timeWindow     = item["time_window"]  as? String ?? "mixed"
        let hasGpsCluster  = Double(item["zone"] != nil ? 1 : 0)
        let ruleConf       = Double(item["confidence"] as? Int ?? 0)

        // One-hot encode categorical feature columns to match training CSV schema
        let featureDict: [String: MLFeatureValue] = [
            "repeat_count_30d":          MLFeatureValue(double: repeatCount),
            "distinct_agent_count":      MLFeatureValue(double: agentCount),
            "is_watchlist":              MLFeatureValue(double: isWatchlist),
            "result_type_allocated":     MLFeatureValue(double: resultType == "allocated_match"  ? 1 : 0),
            "result_type_restricted":    MLFeatureValue(double: resultType == "restricted_match" ? 1 : 0),
            "result_type_conflict":      MLFeatureValue(double: resultType == "conflict"         ? 1 : 0),
            "day_bucket_weekday":        MLFeatureValue(double: dayBucket  == "weekday"  ? 1 : 0),
            "day_bucket_weekend":        MLFeatureValue(double: dayBucket  == "weekend"  ? 1 : 0),
            "day_bucket_both":           MLFeatureValue(double: dayBucket  == "both"     ? 1 : 0),
            "time_window_morning":       MLFeatureValue(double: timeWindow == "morning"   ? 1 : 0),
            "time_window_afternoon":     MLFeatureValue(double: timeWindow == "afternoon" ? 1 : 0),
            "time_window_evening":       MLFeatureValue(double: timeWindow == "evening"   ? 1 : 0),
            "time_window_night":         MLFeatureValue(double: timeWindow == "night"     ? 1 : 0),
            "has_gps_cluster":           MLFeatureValue(double: hasGpsCluster),
            "rule_confidence_score":     MLFeatureValue(double: ruleConf),
        ]

        guard let provider   = try? MLDictionaryFeatureProvider(dictionary: featureDict),
              let prediction = try? model.prediction(from: provider) else { return nil }

        // TabularClassifier emits a column named "<target>Probability" with a
        // dictionary keyed by class label.  Both "1" (String) and 1 (Int64)
        // keys are tried to handle Create ML label encoding differences.
        let probColName = "seen_again_72hProbability"
        if let probDict = prediction.featureValue(for: probColName)?.dictionaryValue {
            if let p = probDict["1"]       as? Double { return max(0, min(1, p)) }
            if let p = probDict[1 as Int64] as? Double { return max(0, min(1, p)) }
        }

        // Fallback: regressor output column
        if let raw = prediction.featureValue(for: "seen_again_72h")?.doubleValue {
            return max(0, min(1, raw))
        }

        return nil
    }

    // MARK: - Network helpers

    private func fetchPatrolItems(webView: WKWebView) async -> [[String: Any]]? {
        guard let url = buildURL(path: "/m/api/lpr/patrol") else { return nil }
        var req = URLRequest(url: url,
                             cachePolicy: .reloadIgnoringLocalCacheData,
                             timeoutInterval: 15)
        req.setValue(AppConfig.userAgent, forHTTPHeaderField: "User-Agent")
        let cookieHdr = await cookieHeader(webView: webView, url: url)
        if !cookieHdr.isEmpty { req.setValue(cookieHdr, forHTTPHeaderField: "Cookie") }

        guard let (data, _) = try? await URLSession.shared.data(for: req),
              let json  = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let items = json["items"] as? [[String: Any]] else { return nil }
        return items
    }

    private func uploadScores(scores: [[String: Any]], webView: WKWebView) async {
        guard let url = buildURL(path: "/m/api/lpr/patrol/scores") else { return }
        let body: [String: Any] = [
            "model_version":     modelVersion,
            "prediction_window": "72h",
            "scores":            scores,
        ]
        guard let bodyData = try? JSONSerialization.data(withJSONObject: body) else { return }
        var req = URLRequest(url: url,
                             cachePolicy: .reloadIgnoringLocalCacheData,
                             timeoutInterval: 15)
        req.httpMethod  = "POST"
        req.httpBody    = bodyData
        req.setValue("application/json",  forHTTPHeaderField: "Content-Type")
        req.setValue(AppConfig.userAgent, forHTTPHeaderField: "User-Agent")
        let cookieHdr = await cookieHeader(webView: webView, url: url)
        if !cookieHdr.isEmpty { req.setValue(cookieHdr, forHTTPHeaderField: "Cookie") }
        _ = try? await URLSession.shared.data(for: req)
    }

    private func buildURL(path: String) -> URL? {
        var comps    = URLComponents()
        comps.scheme = AppConfig.entryURL.scheme
        comps.host   = AppConfig.entryURL.host
        comps.path   = path
        return comps.url
    }

    private func cookieHeader(webView: WKWebView, url: URL) async -> String {
        let all  = await webView.configuration.websiteDataStore.httpCookieStore.allCookies()
        let host = url.host ?? ""
        return all
            .filter { $0.domain.contains(host) || host.contains($0.domain) }
            .map    { "\($0.name)=\($0.value)" }
            .joined(separator: "; ")
    }
}
