import Foundation
import WebKit
import QuickLook
import UIKit

final class DocumentPreviewHandler: NSObject, WKScriptMessageHandler {

    static let shared = DocumentPreviewHandler()
    private override init() { super.init() }

    private weak var webView: WKWebView?
    private var isPresentingDocument = false

    func setWebView(_ wv: WKWebView) {
        self.webView = wv
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        print("[DocPreview] ── JS message received ──")
        print("[DocPreview] body type: \(type(of: message.body))")
        guard let body = message.body as? [String: Any],
              let urlString = body["url"] as? String,
              let filename = body["filename"] as? String else {
            print("[DocPreview] ABORT: could not parse body — body=\(message.body)")
            return
        }
        print("[DocPreview] urlString='\(urlString)', filename='\(filename)'")
        print("[DocPreview] webView nil=\(webView == nil), webView.url=\(webView?.url?.absoluteString ?? "nil")")

        jsDebug("DocumentPreviewHandler: called=YES, url=\(urlString), filename=\(filename)")

        guard !isPresentingDocument else {
            print("[DocPreview] ABORT: already presenting a document (isPresentingDocument=true)")
            return
        }

        let docURL: URL
        if let absolute = URL(string: urlString), absolute.scheme != nil {
            docURL = absolute
            print("[DocPreview] urlString is absolute: \(docURL.absoluteString)")
        } else if let baseURL = webView?.url,
                  let resolved = URL(string: urlString, relativeTo: baseURL)?.absoluteURL {
            docURL = resolved
            print("[DocPreview] resolved relative URL against baseURL=\(baseURL.absoluteString)")
        } else if let fallback = URL(string: urlString) {
            docURL = fallback
            print("[DocPreview] fallback URL parse: \(docURL.absoluteString)")
        } else {
            print("[DocPreview] ABORT: could not build docURL from '\(urlString)' baseURL=\(webView?.url?.absoluteString ?? "nil")")
            return
        }

        print("[DocPreview] resolved docURL=\(docURL.absoluteString)")
        fetchCookiesAndDownload(remoteURL: docURL, filename: filename)
    }

    func previewFile(at url: URL, filename: String) {
        print("[DocPreview] ── previewFile called ──")
        print("[DocPreview] url=\(url.absoluteString), filename=\(filename)")

        guard !isPresentingDocument else {
            print("[DocPreview] ABORT: already presenting a document")
            return
        }

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
            let host = remoteURL.host ?? "nil"
            print("[DocPreview] Total cookies in WK store: \(allCookies.count), target host: '\(host)'")
            let relevantCookies = allCookies.filter { host.hasSuffix($0.domain.trimmingCharacters(in: CharacterSet(charactersIn: "."))) || $0.domain == host }
            print("[DocPreview] Relevant cookies for host: \(relevantCookies.count)")
            for c in relevantCookies {
                print("[DocPreview]   cookie: name='\(c.name)' domain='\(c.domain)' path='\(c.path)' secure=\(c.isSecure)")
            }
            DispatchQueue.main.async {
                self?.downloadAndPreview(remoteURL: remoteURL, filename: filename, cookies: allCookies)
            }
        }
    }

    private func jsDebug(_ msg: String) {
        let escaped = msg.replacingOccurrences(of: "\\", with: "\\\\")
                         .replacingOccurrences(of: "'", with: "\\'")
                         .replacingOccurrences(of: "\n", with: "\\n")
        let js = "if(window._axPdfDebugAppend) window._axPdfDebugAppend('\(escaped)');"
        DispatchQueue.main.async { [weak self] in
            self?.webView?.evaluateJavaScript(js, completionHandler: nil)
        }
    }

    private static func extractFilename(from contentDisposition: String) -> String? {
        let patterns = [
            "filename\\*=(?:UTF-8''|utf-8'')(.+)",
            "filename=\"([^\"]+)\"",
            "filename=([^;\\s]+)"
        ]
        for pattern in patterns {
            if let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive),
               let match = regex.firstMatch(in: contentDisposition, range: NSRange(contentDisposition.startIndex..., in: contentDisposition)),
               match.numberOfRanges > 1,
               let range = Range(match.range(at: 1), in: contentDisposition) {
                let raw = String(contentDisposition[range])
                return raw.removingPercentEncoding ?? raw
            }
        }
        return nil
    }

    private static func extensionForMIME(_ mime: String) -> String? {
        let lower = mime.lowercased().trimmingCharacters(in: .whitespaces)
        let map: [String: String] = [
            "application/pdf": "pdf",
            "application/msword": "doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/vnd.ms-excel": "xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "text/csv": "csv",
            "image/jpeg": "jpg",
            "image/png": "png"
        ]
        for (key, ext) in map {
            if lower.hasPrefix(key) { return ext }
        }
        return nil
    }

    private lazy var noRedirectSession: URLSession = {
        let config = URLSessionConfiguration.default
        let delegate = NoRedirectDelegate()
        return URLSession(configuration: config, delegate: delegate, delegateQueue: nil)
    }()

    private func downloadAndPreview(remoteURL: URL, filename: String, cookies: [HTTPCookie]) {
        print("[DocPreview] ── download started ──")
        print("[DocPreview] URL: \(remoteURL.absoluteString)")
        print("[DocPreview] filename: \(filename)")
        print("[DocPreview] cookies attached: \(cookies.count)")

        var request = URLRequest(url: remoteURL)
        let headers = HTTPCookie.requestHeaderFields(with: cookies)
        for (key, value) in headers {
            request.setValue(value, forHTTPHeaderField: key)
        }

        jsDebug("download started, url=\(remoteURL.absoluteString)")
        noRedirectSession.downloadTask(with: request) { [weak self] tempURL, response, error in
            if let error = error {
                let nsError = error as NSError
                print("[DocPreview] DOWNLOAD FAILED: domain=\(nsError.domain) code=\(nsError.code) desc=\(nsError.localizedDescription)")
                self?.jsDebug("DOWNLOAD FAILED: \(nsError.localizedDescription)")
                DispatchQueue.main.async {
                    self?.showError("Could not download the document. Error: \(nsError.localizedDescription)")
                }
                return
            }

            guard let tempURL = tempURL else {
                print("[DocPreview] DOWNLOAD FAILED: tempURL is nil (no error reported)")
                DispatchQueue.main.async {
                    self?.showError("Download completed but no file was received.")
                }
                return
            }

            print("[DocPreview] tempURL: \(tempURL.path)")

            guard let httpResponse = response as? HTTPURLResponse else {
                print("[DocPreview] WARNING: response is not HTTPURLResponse — type: \(type(of: response))")
                DispatchQueue.main.async {
                    self?.showError("Unexpected server response type.")
                }
                return
            }

            let statusCode = httpResponse.statusCode
            let contentType = httpResponse.value(forHTTPHeaderField: "Content-Type") ?? "unknown"
            let contentLength = httpResponse.value(forHTTPHeaderField: "Content-Length") ?? "unknown"
            let contentDisposition = httpResponse.value(forHTTPHeaderField: "Content-Disposition") ?? "none"
            let finalURL = httpResponse.url?.absoluteString ?? "nil"

            print("[DocPreview] HTTP status: \(statusCode)")
            print("[DocPreview] Content-Type: \(contentType)")
            print("[DocPreview] Content-Length: \(contentLength)")
            print("[DocPreview] Content-Disposition: \(contentDisposition)")
            print("[DocPreview] Final URL: \(finalURL)")
            print("[DocPreview] Request URL: \(remoteURL.absoluteString)")

            if (300...399).contains(statusCode) {
                let location = httpResponse.value(forHTTPHeaderField: "Location") ?? "unknown"
                print("[DocPreview] REDIRECT detected → \(location)")
                let isLoginRedirect = location.contains("/login") || location.contains("/m/login")
                DispatchQueue.main.async {
                    if isLoginRedirect {
                        self?.showError("Your session has expired. Please close this screen, log in again, and retry opening the document.")
                    } else {
                        self?.showError("The server redirected the request to: \(location)")
                    }
                }
                return
            }

            if !(200...299).contains(statusCode) {
                let bodySnippet = (try? String(contentsOf: tempURL, encoding: .utf8))?.prefix(300) ?? "(unreadable)"
                print("[DocPreview] SERVER ERROR: status=\(statusCode), body preview: \(bodySnippet)")
                DispatchQueue.main.async {
                    self?.showError("The server returned an error (\(statusCode)). The file may have been removed or is not accessible.")
                }
                return
            }

            if contentType.contains("text/html") {
                let snippet = (try? String(contentsOf: tempURL, encoding: .utf8))?.prefix(500) ?? ""
                print("[DocPreview] WARNING: Server returned HTML instead of document file")
                print("[DocPreview] HTML body preview: \(snippet)")
                DispatchQueue.main.async {
                    self?.showError("The server returned a web page instead of the document file. This usually means the download token has expired or the session is invalid.")
                }
                return
            }

            let fileSize: Int
            do {
                let attrs = try FileManager.default.attributesOfItem(atPath: tempURL.path)
                fileSize = (attrs[.size] as? Int) ?? 0
            } catch {
                print("[DocPreview] Could not read file attributes: \(error)")
                fileSize = 0
            }

            print("[DocPreview] Downloaded file size: \(fileSize) bytes")

            if fileSize == 0 {
                print("[DocPreview] ABORT: Downloaded file is empty (0 bytes)")
                DispatchQueue.main.async {
                    self?.showError("The downloaded document is empty (0 bytes). Please contact an admin to check this attachment.")
                }
                return
            }

            var resolvedFilename = filename
            if let cdFilename = Self.extractFilename(from: contentDisposition), !cdFilename.isEmpty {
                print("[DocPreview] Using filename from Content-Disposition: '\(cdFilename)'")
                resolvedFilename = cdFilename
            } else if URL(fileURLWithPath: filename).pathExtension.isEmpty {
                let mimeExt = Self.extensionForMIME(contentType)
                if let ext = mimeExt {
                    resolvedFilename = filename + "." + ext
                    print("[DocPreview] Appended extension from MIME: '\(resolvedFilename)'")
                }
            }

            let tmpDir = FileManager.default.temporaryDirectory
                .appendingPathComponent("docpreview", isDirectory: true)
            do {
                try FileManager.default.createDirectory(at: tmpDir, withIntermediateDirectories: true)
            } catch {
                print("[DocPreview] Failed to create temp directory: \(error)")
            }

            let destURL = tmpDir.appendingPathComponent(resolvedFilename)
            print("[DocPreview] Destination path: \(destURL.path)")
            print("[DocPreview] Destination extension: \(destURL.pathExtension)")

            try? FileManager.default.removeItem(at: destURL)

            do {
                try FileManager.default.moveItem(at: tempURL, to: destURL)
            } catch {
                print("[DocPreview] FAILED to move file: \(error)")
                DispatchQueue.main.async {
                    self?.showError("Could not prepare the document for viewing: \(error.localizedDescription)")
                }
                return
            }

            let fileExists = FileManager.default.fileExists(atPath: destURL.path)
            let finalSize: Int
            do {
                let attrs = try FileManager.default.attributesOfItem(atPath: destURL.path)
                finalSize = (attrs[.size] as? Int) ?? 0
            } catch {
                finalSize = 0
            }

            print("[DocPreview] ── pre-preview checks ──")
            print("[DocPreview] File exists at dest: \(fileExists)")
            print("[DocPreview] File size at dest: \(finalSize) bytes")
            print("[DocPreview] File extension: \(destURL.pathExtension)")
            print("[DocPreview] File URL: \(destURL.absoluteString)")

            guard fileExists && finalSize > 0 else {
                print("[DocPreview] ABORT: file missing or empty after move")
                DispatchQueue.main.async {
                    self?.showError("Document file is missing or empty after save.")
                }
                return
            }

            self?.jsDebug("file_downloaded=YES, size=\(finalSize)bytes, ext=\(destURL.pathExtension)")
            DispatchQueue.main.async {
                print("[DocPreview] ── presenting document ──")
                self?.presentDocument(fileURL: destURL, filename: resolvedFilename)
            }
        }.resume()
    }

    private func presentDocument(fileURL: URL, filename: String) {
        guard !isPresentingDocument else {
            print("[DocPreview] ABORT presentDocument: already presenting (guard)")
            return
        }

        guard let vc = topViewController() else {
            print("[DocPreview] ABORT presentDocument: no topViewController found")
            return
        }

        print("[DocPreview] topViewController: \(type(of: vc))")
        print("[DocPreview] presenting DocumentContainerController for: \(fileURL.lastPathComponent)")

        isPresentingDocument = true

        jsDebug("QLPreviewController present() attempted=YES, topVC=\(type(of: vc))")

        let viewer = DocumentContainerController(fileURL: fileURL, filename: filename) { [weak self] in
            print("[DocPreview] Document viewer dismissed (onDismiss callback)")
            self?.isPresentingDocument = false
        }
        viewer.modalPresentationStyle = .fullScreen
        vc.present(viewer, animated: true) { [weak self] in
            print("[DocPreview] Document viewer presented successfully")
            self?.jsDebug("QLPreviewController visible=YES")
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { [weak self] in
            guard let self = self else { return }
            if self.isPresentingDocument, vc.presentedViewController == nil {
                print("[DocPreview] WARNING: presentation appears to have failed — resetting isPresentingDocument")
                self.isPresentingDocument = false
            }
        }
    }

    private func showError(_ message: String) {
        print("[DocPreview] SHOWING ERROR ALERT: \(message)")
        guard let vc = topViewController() else {
            print("[DocPreview] Cannot show error — no topViewController")
            return
        }
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
    private let onDismiss: () -> Void

    init(fileURL: URL, filename: String, onDismiss: @escaping () -> Void) {
        self.fileURL = fileURL
        self.filename = filename
        self.onDismiss = onDismiss
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    deinit {
        try? FileManager.default.removeItem(at: fileURL)
        onDismiss()
        print("[DocPreview] DocumentContainerController deinit — cleaned up \(fileURL.lastPathComponent)")
    }

    private var toolbarView: UIView?

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground

        print("[DocPreview][Layout] viewDidLoad START")
        print("[DocPreview][Layout] fileURL=\(fileURL.path)")
        print("[DocPreview][Layout] file exists=\(FileManager.default.fileExists(atPath: fileURL.path))")

        let coord = QLPreviewCoordinator(fileURL: fileURL)
        self.coordinator = coord

        let ql = QLPreviewController()
        ql.dataSource = coord
        ql.delegate = coord
        self.qlController = ql

        addChild(ql)
        ql.view.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(ql.view)
        ql.didMove(toParent: self)

        let bar = UIView()
        bar.translatesAutoresizingMaskIntoConstraints = false
        bar.backgroundColor = .systemBackground
        bar.layer.zPosition = 9999
        self.toolbarView = bar

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
        titleLabel.textAlignment = .center

        let doneBtn = UIButton(type: .system)
        doneBtn.translatesAutoresizingMaskIntoConstraints = false
        doneBtn.setTitle("Done", for: .normal)
        doneBtn.titleLabel?.font = .systemFont(ofSize: 17, weight: .semibold)
        doneBtn.addTarget(self, action: #selector(doneTapped), for: .touchUpInside)

        let shareBtn = UIButton(type: .system)
        shareBtn.translatesAutoresizingMaskIntoConstraints = false
        shareBtn.setImage(UIImage(systemName: "square.and.arrow.up"), for: .normal)
        shareBtn.addTarget(self, action: #selector(shareTapped), for: .touchUpInside)
        shareBtn.tintColor = .systemBlue

        bar.addSubview(doneBtn)
        bar.addSubview(titleLabel)
        bar.addSubview(shareBtn)
        bar.addSubview(separator)
        view.addSubview(bar)

        let rowHeight: CGFloat = 44

        NSLayoutConstraint.activate([
            bar.topAnchor.constraint(equalTo: view.topAnchor),
            bar.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            bar.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            bar.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: rowHeight),

            doneBtn.leadingAnchor.constraint(equalTo: bar.leadingAnchor, constant: 16),
            doneBtn.bottomAnchor.constraint(equalTo: bar.bottomAnchor, constant: -8),
            doneBtn.heightAnchor.constraint(equalToConstant: 28),

            titleLabel.centerXAnchor.constraint(equalTo: bar.centerXAnchor),
            titleLabel.centerYAnchor.constraint(equalTo: doneBtn.centerYAnchor),
            titleLabel.leadingAnchor.constraint(greaterThanOrEqualTo: doneBtn.trailingAnchor, constant: 8),
            titleLabel.trailingAnchor.constraint(lessThanOrEqualTo: shareBtn.leadingAnchor, constant: -8),

            shareBtn.trailingAnchor.constraint(equalTo: bar.trailingAnchor, constant: -16),
            shareBtn.centerYAnchor.constraint(equalTo: doneBtn.centerYAnchor),
            shareBtn.widthAnchor.constraint(equalToConstant: 28),
            shareBtn.heightAnchor.constraint(equalToConstant: 28),

            separator.leadingAnchor.constraint(equalTo: bar.leadingAnchor),
            separator.trailingAnchor.constraint(equalTo: bar.trailingAnchor),
            separator.bottomAnchor.constraint(equalTo: bar.bottomAnchor),
            separator.heightAnchor.constraint(equalToConstant: 0.5),

            ql.view.topAnchor.constraint(equalTo: bar.bottomAnchor),
            ql.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            ql.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            ql.view.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])

        view.bringSubviewToFront(bar)

        print("[DocPreview][Layout] viewDidLoad COMPLETE — bar, QL child added")
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        if let bar = toolbarView {
            view.bringSubviewToFront(bar)
            let frame = bar.frame
            print("[DocPreview][Layout] viewDidAppear — bar frame=\(frame)")
            print("[DocPreview][Layout] bar.isHidden=\(bar.isHidden) alpha=\(bar.alpha)")
            print("[DocPreview][Layout] bar subview count=\(bar.subviews.count)")
            for (i, sv) in bar.subviews.enumerated() {
                print("[DocPreview][Layout]   subview[\(i)] \(type(of: sv)) frame=\(sv.frame) hidden=\(sv.isHidden) alpha=\(sv.alpha)")
            }
        }
        if let ql = qlController {
            print("[DocPreview][Layout] QLPreviewController visible=\(ql.isViewLoaded && ql.view.window != nil)")
            print("[DocPreview][Layout] QLPreviewController view frame=\(ql.view.frame)")
            print("[DocPreview][Layout] QL navigationController=\(ql.navigationController != nil)")
            if let nav = ql.navigationController {
                print("[DocPreview][Layout] QL navBar hidden=\(nav.isNavigationBarHidden)")
                print("[DocPreview][Layout] QL navBar frame=\(nav.navigationBar.frame)")
            }
        }
        print("[DocPreview][Layout] self.view frame=\(view.frame)")
        print("[DocPreview][Layout] self.presentingViewController=\(presentingViewController != nil)")
    }

    @objc private func doneTapped() {
        dismiss(animated: true) { [weak self] in
            guard let self = self else { return }
            try? FileManager.default.removeItem(at: self.fileURL)
            self.onDismiss()
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

private final class QLPreviewCoordinator: NSObject, QLPreviewControllerDataSource, QLPreviewControllerDelegate {
    let fileURL: URL

    init(fileURL: URL) {
        self.fileURL = fileURL
        super.init()
    }

    func numberOfPreviewItems(in controller: QLPreviewController) -> Int {
        print("[DocPreview] QLPreview numberOfPreviewItems called → 1")
        return 1
    }

    func previewController(_ controller: QLPreviewController, previewItemAt index: Int) -> QLPreviewItem {
        print("[DocPreview] QLPreview previewItemAt \(index) → \(fileURL.path)")
        print("[DocPreview] File exists: \(FileManager.default.fileExists(atPath: fileURL.path))")
        return fileURL as QLPreviewItem
    }

    func previewController(_ controller: QLPreviewController, didUpdateContentsOf previewItem: QLPreviewItem) {
        print("[DocPreview] QLPreview didUpdateContents")
    }

    func previewControllerDidDismiss(_ controller: QLPreviewController) {
        print("[DocPreview] QLPreview dismissed by system")
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
        let location = response.value(forHTTPHeaderField: "Location") ?? "unknown"
        print("[DocPreview] NoRedirect: blocked redirect to \(location)")
        completionHandler(nil)
    }
}
