import UIKit

class OfflineViewController: UIViewController {

    var onRetry: (() -> Void)?

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .white
        setupUI()
    }

    // MARK: - UI

    private func setupUI() {
        let stack = UIStackView()
        stack.axis = .vertical
        stack.alignment = .center
        stack.spacing = 16
        stack.translatesAutoresizingMaskIntoConstraints = false

        // Icon
        let iconView = UIImageView()
        let config = UIImage.SymbolConfiguration(pointSize: 48, weight: .light)
        iconView.image = UIImage(systemName: "wifi.slash", withConfiguration: config)
        iconView.tintColor = UIColor(red: 0.18, green: 0.39, blue: 0.92, alpha: 1.0) // #2563EB
        iconView.contentMode = .scaleAspectFit
        iconView.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            iconView.widthAnchor.constraint(equalToConstant: 64),
            iconView.heightAnchor.constraint(equalToConstant: 64),
        ])

        // Title
        let titleLabel = UILabel()
        titleLabel.text = "Unable to Connect"
        titleLabel.font = .systemFont(ofSize: 20, weight: .semibold)
        titleLabel.textColor = UIColor(red: 0.07, green: 0.07, blue: 0.07, alpha: 1.0)
        titleLabel.textAlignment = .center

        // Message
        let msgLabel = UILabel()
        msgLabel.text = AppConfig.offlineMessage
        msgLabel.font = .systemFont(ofSize: 15, weight: .regular)
        msgLabel.textColor = UIColor(red: 0.42, green: 0.44, blue: 0.50, alpha: 1.0)
        msgLabel.textAlignment = .center
        msgLabel.numberOfLines = 0

        // Retry button
        let retryButton = UIButton(type: .system)
        retryButton.setTitle("Try Again", for: .normal)
        retryButton.titleLabel?.font = .systemFont(ofSize: 16, weight: .semibold)
        retryButton.setTitleColor(.white, for: .normal)
        retryButton.backgroundColor = UIColor(red: 0.15, green: 0.39, blue: 0.92, alpha: 1.0)
        retryButton.layer.cornerRadius = 12
        retryButton.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            retryButton.heightAnchor.constraint(equalToConstant: 48),
            retryButton.widthAnchor.constraint(equalToConstant: 180),
        ])
        retryButton.addTarget(self, action: #selector(retryTapped), for: .touchUpInside)

        stack.addArrangedSubview(iconView)
        stack.addArrangedSubview(titleLabel)
        stack.addArrangedSubview(msgLabel)
        stack.setCustomSpacing(24, after: msgLabel)
        stack.addArrangedSubview(retryButton)

        view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: view.centerYAnchor, constant: -20),
            stack.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 40),
            stack.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -40),
        ])
    }

    @objc private func retryTapped() {
        onRetry?()
    }
}
