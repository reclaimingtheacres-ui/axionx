import Foundation
import WebKit
import QuickLook
import UIKit

final class DocumentPreviewHandler: NSObject, WKScriptMessageHandler {

    static let shared = DocumentPreviewHandler()
    private override init() { super.init() }

    private weak var webView: WKWebView?

    func setWebView(_ wv: WKWebView) {
        self.webView = wv
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard let body = message.body as? [String: Any],
              let urlString = body["url"] as? String,
              let filename = body["filename"] as? String else { return }

        guard let baseURL = webView?.url,
              let docURL = URL(string: urlString, relativeTo: baseURL)?.absoluteURL ?? URL(string: urlString) else { return }

        print("[DocPreview] Opening: \(docURL.absoluteString), filename: \(filename)")
        fetchCookiesAndDownload(remoteURL: docURL, filename: filename)
    }

    func previewFile(at url: URL, filename: String) {
        print("[DocPreview] previewFile: \(url.absoluteString), filename: \(filename)")
        fetchCookiesAndDownload(remoteURL: url, filename: filename)
    }

    private func fetchCookiesAndDownload(remoteURL: URL, filename: String) {
        guard let cookieStore = webView?.configuration.websiteDataStore.httpCookieStore else {
            downloadAndPreview(remoteURL: remoteURL, filename: filename, cookies: [])
            return
        }

        cookieStore.getAllCookies { [weak self] allCookies in
            let relevant = allCookies.filter { cookie in
                guard let host = remoteURL.host else { return false }
                let cookieDomain = cookie.domain.hasPrefix(".") ? String(cookie.domain.dropFirst()) : cookie.domain
                return host == cookieDomain || host.hasSuffix("." + cookieDomain)
            }
            DispatchQueue.main.async {
                self?.downloadAndPreview(remoteURL: remoteURL, filename: filename, cookies: relevant)
            }
        }
    }

    private func downloadAndPreview(remoteURL: URL, filename: String, cookies: [HTTPCookie]) {
        var request = URLRequest(url: remoteURL)
        let headers = HTTPCookie.requestHeaderFields(with: cookies)
        for (key, value) in headers {
            request.setValue(value, forHTTPHeaderField: key)
        }

        URLSession.shared.downloadTask(with: request) { [weak self] tempURL, response, error in
            guard let tempURL = tempURL, error == nil else {
                print("[DocPreview] Download failed: \(error?.localizedDescription ?? "unknown")")
                DispatchQueue.main.async {
                    self?.showError("Could not download the document. Please check your connection and try again.")
                }
                return
            }

            if let httpResponse = response as? HTTPURLResponse {
                let contentType = httpResponse.value(forHTTPHeaderField: "Content-Type") ?? "unknown"
                print("[DocPreview] HTTP \(httpResponse.statusCode), Content-Type: \(contentType), URL: \(remoteURL.absoluteString)")

                if !(200...299).contains(httpResponse.statusCode) {
                    print("[DocPreview] Server returned status \(httpResponse.statusCode)")
                    DispatchQueue.main.async {
                        self?.showError("The server returned an error (\(httpResponse.statusCode)). The file may have been removed or is not accessible.")
                    }
                    return
                }

                if contentType.contains("text/html") {
                    let snippet = (try? String(contentsOf: tempURL, encoding: .utf8))?.prefix(200) ?? ""
                    print("[DocPreview] WARNING: Server returned HTML instead of a document. Body preview: \(snippet)")
                    DispatchQueue.main.async {
                        self?.showError("The server returned a web page instead of the document file. The file may be missing or require re-upload.")
                    }
                    return
                }
            }

            let fileSize = (try? FileManager.default.attributesOfItem(atPath: tempURL.path)[.size] as? Int) ?? 0
            print("[DocPreview] Downloaded \(fileSize) bytes for \(filename)")
            if fileSize == 0 {
                print("[DocPreview] Downloaded file is empty")
                DispatchQueue.main.async {
                    self?.showError("The downloaded document is empty (0 bytes). Please contact an admin to check this attachment.")
                }
                return
            }

            let tmpDir = FileManager.default.temporaryDirectory
                .appendingPathComponent("docpreview", isDirectory: true)
            try? FileManager.default.createDirectory(at: tmpDir, withIntermediateDirectories: true)

            let destURL = tmpDir.appendingPathComponent(filename)
            try? FileManager.default.removeItem(at: destURL)

            do {
                try FileManager.default.moveItem(at: tempURL, to: destURL)
            } catch {
                print("[DocPreview] Failed to move file: \(error)")
                DispatchQueue.main.async {
                    self?.showError("Could not prepare the document for viewing.")
                }
                return
            }

            print("[DocPreview] File ready at: \(destURL.path)")

            DispatchQueue.main.async {
                self?.presentQuickLook(fileURL: destURL, filename: filename)
            }
        }.resume()
    }

    private func presentQuickLook(fileURL: URL, filename: String) {
        guard let vc = topViewController() else {
            print("[DocPreview] No view controller to present document viewer")
            return
        }

        let coordinator = QLPreviewCoordinator(fileURL: fileURL)
        let qlController = QLPreviewController()
        qlController.dataSource = coordinator
        qlController.delegate = coordinator

        objc_setAssociatedObject(qlController, &AssociatedKeys.coordinator, coordinator, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)

        let nav = UINavigationController(rootViewController: qlController)
        nav.modalPresentationStyle = .fullScreen

        let displayName: String
        if filename.count > 40 {
            let start = filename.prefix(20)
            let ext = (filename as NSString).pathExtension
            displayName = start + "…." + ext
        } else {
            displayName = filename
        }
        qlController.title = displayName

        qlController.navigationItem.rightBarButtonItem = UIBarButtonItem(
            barButtonSystemItem: .done,
            target: coordinator,
            action: #selector(QLPreviewCoordinator.dismissViewer)
        )

        vc.present(nav, animated: true)
    }

    private func showError(_ message: String) {
        guard let vc = topViewController() else { return }
        let alert = UIAlertController(title: "Document Error", message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        vc.present(alert, animated: true)
    }

    private func topViewController() -> UIViewController? {
        guard let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let window = scene.keyWindow else { return nil }
        var vc = window.rootViewController
        while let presented = vc?.presentedViewController { vc = presented }
        return vc
    }
}

private enum AssociatedKeys {
    static var coordinator: UInt8 = 0
}

private final class QLPreviewCoordinator: NSObject, QLPreviewControllerDataSource, QLPreviewControllerDelegate {
    let fileURL: URL

    init(fileURL: URL) {
        self.fileURL = fileURL
        super.init()
    }

    func numberOfPreviewItems(in controller: QLPreviewController) -> Int { 1 }

    func previewController(_ controller: QLPreviewController, previewItemAt index: Int) -> QLPreviewItem {
        fileURL as QLPreviewItem
    }

    func previewController(_ controller: QLPreviewController, shouldOpen url: URL, for item: QLPreviewItem) -> Bool {
        return false
    }

    @objc func dismissViewer() {
        guard let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let window = scene.keyWindow else { return }
        var vc = window.rootViewController
        while let presented = vc?.presentedViewController { vc = presented }
        vc?.dismiss(animated: true) { [weak self] in
            guard let self = self else { return }
            try? FileManager.default.removeItem(at: self.fileURL)
        }
    }

    func previewControllerDidDismiss(_ controller: QLPreviewController) {
        try? FileManager.default.removeItem(at: fileURL)
    }
}
