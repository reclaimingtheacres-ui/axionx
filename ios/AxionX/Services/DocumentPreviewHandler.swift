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
        print("[DocPreview] Handler fired, body type: \(type(of: message.body))")
        guard let body = message.body as? [String: Any],
              let urlString = body["url"] as? String,
              let filename = body["filename"] as? String else {
            print("[DocPreview] Guard failed: could not parse body")
            return
        }
        print("[DocPreview] urlString=\(urlString), filename=\(filename), webView nil=\(webView == nil)")

        guard let baseURL = webView?.url,
              let docURL = URL(string: urlString, relativeTo: baseURL)?.absoluteURL ?? URL(string: urlString) else {
            print("[DocPreview] Guard failed: baseURL=\(String(describing: webView?.url)), could not build docURL from '\(urlString)'")
            return
        }

        print("[DocPreview] Opening: \(docURL.absoluteString), filename: \(filename)")
        fetchCookiesAndDownload(remoteURL: docURL, filename: filename)
    }

    func previewFile(at url: URL, filename: String) {
        print("[DocPreview] previewFile: \(url.absoluteString), filename: \(filename)")
        fetchCookiesAndDownload(remoteURL: url, filename: filename)
    }

    private func fetchCookiesAndDownload(remoteURL: URL, filename: String) {
        guard let wv = webView else {
            print("[DocPreview] WARNING: webView is nil — falling back to shared cookie storage")
            let sharedCookies = HTTPCookieStorage.shared.cookies ?? []
            print("[DocPreview] Shared cookie storage has \(sharedCookies.count) cookies")
            downloadAndPreview(remoteURL: remoteURL, filename: filename, cookies: sharedCookies)
            return
        }
        let cookieStore = wv.configuration.websiteDataStore.httpCookieStore

        cookieStore.getAllCookies { [weak self] allCookies in
            print("[DocPreview] Total cookies in store: \(allCookies.count), target host: '\(remoteURL.host ?? "nil")'")
            for c in allCookies {
                print("[DocPreview]   cookie: name='\(c.name)' domain='\(c.domain)' path='\(c.path)'")
            }
            DispatchQueue.main.async {
                self?.downloadAndPreview(remoteURL: remoteURL, filename: filename, cookies: allCookies)
            }
        }
    }

    private lazy var noRedirectSession: URLSession = {
        let config = URLSessionConfiguration.default
        let delegate = NoRedirectDelegate()
        return URLSession(configuration: config, delegate: delegate, delegateQueue: nil)
    }()

    private func downloadAndPreview(remoteURL: URL, filename: String, cookies: [HTTPCookie]) {
        var request = URLRequest(url: remoteURL)
        let headers = HTTPCookie.requestHeaderFields(with: cookies)
        for (key, value) in headers {
            request.setValue(value, forHTTPHeaderField: key)
        }

        print("[DocPreview] Starting download: \(remoteURL.absoluteString), cookies attached: \(cookies.count)")
        noRedirectSession.downloadTask(with: request) { [weak self] tempURL, response, error in
            guard let tempURL = tempURL, error == nil else {
                print("[DocPreview] Download failed: \(error?.localizedDescription ?? "unknown")")
                DispatchQueue.main.async {
                    self?.showError("Could not download the document. Please check your connection and try again.")
                }
                return
            }

            if let httpResponse = response as? HTTPURLResponse {
                let contentType = httpResponse.value(forHTTPHeaderField: "Content-Type") ?? "unknown"
                let finalURL = httpResponse.url?.absoluteString ?? "nil"
                print("[DocPreview] HTTP \(httpResponse.statusCode), Content-Type: \(contentType), finalURL: \(finalURL), requestURL: \(remoteURL.absoluteString)")

                if (300...399).contains(httpResponse.statusCode) {
                    let location = httpResponse.value(forHTTPHeaderField: "Location") ?? "unknown"
                    print("[DocPreview] Redirect detected → \(location)")
                    let isLoginRedirect = location.contains("/login") || location.contains("/m/login")
                    DispatchQueue.main.async {
                        if isLoginRedirect {
                            self?.showError("Your session has expired. Please close this screen, log in again, and retry opening the document.")
                        } else {
                            self?.showError("The server redirected the request. The file may have been moved or is not accessible.")
                        }
                    }
                    return
                }

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

            print("[DocPreview] File ready at: \(destURL.path), ext: \(destURL.pathExtension)")

            DispatchQueue.main.async {
                self?.presentDocument(fileURL: destURL, filename: filename)
            }
        }.resume()
    }

    private func presentDocument(fileURL: URL, filename: String) {
        guard let vc = topViewController() else {
            print("[DocPreview] No view controller to present document viewer")
            return
        }

        let viewer = DocumentContainerController(fileURL: fileURL, filename: filename)
        viewer.modalPresentationStyle = .fullScreen
        vc.present(viewer, animated: true)
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

private final class DocumentContainerController: UIViewController {
    private let fileURL: URL
    private let filename: String
    private var qlController: QLPreviewController?
    private var coordinator: QLPreviewCoordinator?

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
        view.backgroundColor = .systemBackground

        let bar = UIView()
        bar.translatesAutoresizingMaskIntoConstraints = false
        bar.backgroundColor = .systemBackground

        let separator = UIView()
        separator.translatesAutoresizingMaskIntoConstraints = false
        separator.backgroundColor = .separator

        let displayName: String
        if filename.count > 35 {
            let start = filename.prefix(18)
            let ext = (filename as NSString).pathExtension
            displayName = start + "…." + ext
        } else {
            displayName = filename
        }

        let titleLabel = UILabel()
        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        titleLabel.text = displayName
        titleLabel.font = .systemFont(ofSize: 15, weight: .semibold)
        titleLabel.textColor = .label
        titleLabel.lineBreakMode = .byTruncatingMiddle

        let shareBtn = UIButton(type: .system)
        shareBtn.translatesAutoresizingMaskIntoConstraints = false
        shareBtn.setImage(UIImage(systemName: "square.and.arrow.up"), for: .normal)
        shareBtn.addTarget(self, action: #selector(shareTapped), for: .touchUpInside)
        shareBtn.tintColor = .systemBlue

        let doneBtn = UIButton(type: .system)
        doneBtn.translatesAutoresizingMaskIntoConstraints = false
        doneBtn.setTitle("Done", for: .normal)
        doneBtn.titleLabel?.font = .systemFont(ofSize: 17, weight: .semibold)
        doneBtn.addTarget(self, action: #selector(doneTapped), for: .touchUpInside)

        bar.addSubview(shareBtn)
        bar.addSubview(titleLabel)
        bar.addSubview(doneBtn)
        bar.addSubview(separator)
        view.addSubview(bar)

        let rowHeight: CGFloat = 44

        NSLayoutConstraint.activate([
            bar.topAnchor.constraint(equalTo: view.topAnchor),
            bar.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            bar.trailingAnchor.constraint(equalTo: view.trailingAnchor),

            shareBtn.leadingAnchor.constraint(equalTo: bar.leadingAnchor, constant: 16),
            shareBtn.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 8),
            shareBtn.widthAnchor.constraint(equalToConstant: 28),
            shareBtn.heightAnchor.constraint(equalToConstant: 28),

            titleLabel.leadingAnchor.constraint(equalTo: shareBtn.trailingAnchor, constant: 12),
            titleLabel.trailingAnchor.constraint(lessThanOrEqualTo: doneBtn.leadingAnchor, constant: -12),
            titleLabel.centerYAnchor.constraint(equalTo: shareBtn.centerYAnchor),

            doneBtn.trailingAnchor.constraint(equalTo: bar.trailingAnchor, constant: -16),
            doneBtn.centerYAnchor.constraint(equalTo: shareBtn.centerYAnchor),

            bar.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: rowHeight),

            separator.leadingAnchor.constraint(equalTo: bar.leadingAnchor),
            separator.trailingAnchor.constraint(equalTo: bar.trailingAnchor),
            separator.bottomAnchor.constraint(equalTo: bar.bottomAnchor),
            separator.heightAnchor.constraint(equalToConstant: 0.5)
        ])

        let coord = QLPreviewCoordinator(fileURL: fileURL)
        self.coordinator = coord

        let ql = QLPreviewController()
        ql.dataSource = coord
        self.qlController = ql

        let nav = UINavigationController(rootViewController: ql)
        nav.isNavigationBarHidden = true

        addChild(nav)
        nav.view.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(nav.view)
        nav.didMove(toParent: self)

        NSLayoutConstraint.activate([
            nav.view.topAnchor.constraint(equalTo: bar.bottomAnchor),
            nav.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            nav.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            nav.view.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])

        view.bringSubviewToFront(bar)
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
            popover.sourceView = view
            popover.sourceRect = CGRect(x: 30, y: 60, width: 1, height: 1)
        }
        present(activityVC, animated: true)
    }
}

private final class QLPreviewCoordinator: NSObject, QLPreviewControllerDataSource {
    let fileURL: URL

    init(fileURL: URL) {
        self.fileURL = fileURL
        super.init()
    }

    func numberOfPreviewItems(in controller: QLPreviewController) -> Int { 1 }

    func previewController(_ controller: QLPreviewController, previewItemAt index: Int) -> QLPreviewItem {
        fileURL as QLPreviewItem
    }
}

private final class NoRedirectDelegate: NSObject, URLSessionTaskDelegate {
    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        completionHandler(nil)
    }
}
