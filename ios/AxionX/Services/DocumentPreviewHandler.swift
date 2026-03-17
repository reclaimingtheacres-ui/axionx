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

        fetchCookiesAndDownload(remoteURL: docURL, filename: filename)
    }

    func previewFile(at url: URL, filename: String) {
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
                return
            }

            if let httpResponse = response as? HTTPURLResponse,
               !(200...299).contains(httpResponse.statusCode) {
                print("[DocPreview] Server returned status \(httpResponse.statusCode)")
                return
            }

            let fileSize = (try? FileManager.default.attributesOfItem(atPath: tempURL.path)[.size] as? Int) ?? 0
            if fileSize == 0 {
                print("[DocPreview] Downloaded file is empty")
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
                return
            }

            DispatchQueue.main.async {
                self?.presentDocument(fileURL: destURL, filename: filename)
            }
        }.resume()
    }

    private static let qlNativeExtensions: Set<String> = ["pdf", "png", "jpg", "jpeg", "gif", "heic", "heif", "tiff", "bmp"]

    private func presentDocument(fileURL: URL, filename: String) {
        guard let vc = topViewController() else {
            print("[DocPreview] No view controller to present document viewer")
            return
        }

        let ext = fileURL.pathExtension.lowercased()

        if Self.qlNativeExtensions.contains(ext) {
            presentQuickLook(fileURL: fileURL, on: vc)
        } else {
            presentWebDocViewer(fileURL: fileURL, filename: filename, on: vc)
        }
    }

    private func presentQuickLook(fileURL: URL, on vc: UIViewController) {
        let coordinator = QLPreviewCoordinator(fileURL: fileURL)
        let qlController = QLPreviewController()
        qlController.dataSource = coordinator
        qlController.delegate = coordinator
        qlController.modalPresentationStyle = .fullScreen

        objc_setAssociatedObject(qlController, &AssociatedKeys.coordinator, coordinator, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)

        vc.present(qlController, animated: true)
    }

    private func presentWebDocViewer(fileURL: URL, filename: String, on vc: UIViewController) {
        let viewer = DocumentViewerController(fileURL: fileURL, filename: filename)
        let nav = UINavigationController(rootViewController: viewer)
        nav.modalPresentationStyle = .fullScreen
        vc.present(nav, animated: true)
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

    func previewControllerDidDismiss(_ controller: QLPreviewController) {
        try? FileManager.default.removeItem(at: fileURL)
    }
}

private final class DocumentViewerController: UIViewController {
    private let fileURL: URL
    private let filename: String
    private var docWebView: WKWebView!

    init(fileURL: URL, filename: String) {
        self.fileURL = fileURL
        self.filename = filename
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    deinit {
        try? FileManager.default.removeItem(at: fileURL)
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        view.backgroundColor = .white

        let displayName: String
        if filename.count > 40 {
            let start = filename.prefix(20)
            let ext = (filename as NSString).pathExtension
            displayName = start + "…." + ext
        } else {
            displayName = filename
        }
        title = displayName

        navigationItem.rightBarButtonItem = UIBarButtonItem(
            barButtonSystemItem: .done,
            target: self,
            action: #selector(doneTapped)
        )

        navigationItem.leftBarButtonItem = UIBarButtonItem(
            image: UIImage(systemName: "square.and.arrow.up"),
            style: .plain,
            target: self,
            action: #selector(shareTapped)
        )

        let config = WKWebViewConfiguration()

        docWebView = WKWebView(frame: .zero, configuration: config)
        docWebView.translatesAutoresizingMaskIntoConstraints = false
        docWebView.backgroundColor = .white
        docWebView.isOpaque = true
        view.addSubview(docWebView)

        NSLayoutConstraint.activate([
            docWebView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            docWebView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            docWebView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            docWebView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])

        let dir = fileURL.deletingLastPathComponent()
        docWebView.loadFileURL(fileURL, allowingReadAccessTo: dir)
    }

    @objc private func doneTapped() {
        dismiss(animated: true) { [weak self] in
            guard let self = self else { return }
            try? FileManager.default.removeItem(at: self.fileURL)
        }
    }

    @objc private func shareTapped() {
        let activityVC = UIActivityViewController(activityItems: [fileURL], applicationActivities: nil)
        if let popover = activityVC.popoverPresentationController {
            popover.barButtonItem = navigationItem.leftBarButtonItem
        }
        present(activityVC, animated: true)
    }
}
