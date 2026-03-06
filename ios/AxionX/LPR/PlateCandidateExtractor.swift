import Vision

/// Extracts and scores likely plate strings from Vision text observations.
enum PlateCandidateExtractor {

    /// Normalise raw text: uppercase, alphanumeric only.
    static func normalisePlate(_ text: String) -> String {
        text.uppercased().filter { $0.isLetter || $0.isNumber }
    }

    /// Returns true when the string is a plausible Australian-style registration.
    static func isLikelyPlate(_ plate: String) -> Bool {
        guard plate.count >= 4, plate.count <= 8 else { return false }
        let hasLetter = plate.contains { $0.isLetter }
        let hasNumber = plate.contains { $0.isNumber }
        return hasLetter && hasNumber
    }

    /// Extract the best plate candidate from a set of Vision text observations.
    /// Returns nil if no confident candidate is found.
    static func bestCandidate(from observations: [VNRecognizedTextObservation],
                              minimumConfidence: Float = 0.55) -> String? {
        var candidates: [(text: String, confidence: Float)] = []

        for obs in observations {
            guard let top = obs.topCandidates(3).first else { continue }
            let norm = normalisePlate(top.string)
            guard isLikelyPlate(norm) else { continue }
            candidates.append((norm, top.confidence))
        }

        // Sort by confidence descending, then pick the top
        candidates.sort { $0.confidence > $1.confidence }
        guard let best = candidates.first, best.confidence >= minimumConfidence else {
            return nil
        }
        return best.text
    }
}
