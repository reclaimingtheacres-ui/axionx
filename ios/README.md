# AxionX iOS — SwiftUI WKWebView Wrapper

Native iPhone app wrapping the AxionX `/m/*` mobile web routes.
Uses SwiftUI App lifecycle with `UIViewRepresentable` WKWebView, Network framework connectivity monitoring, CoreLocation permission handling, and a clean folder structure ready for native screen expansion.

---

## Open in Xcode

```bash
open ios/AxionX.xcodeproj
```

Requires **Xcode 15+**, Swift 5, iOS 16+ deployment target.

---

## Before You Build

### 1. Set the Debug URL (`Config/AppConfig.swift`)

```swift
static let debugBaseURL = "https://YOUR-REPLIT-PROJECT.replit.app"
```

Replace `YOUR-REPLIT-PROJECT` with your actual Replit project subdomain.  
Also add it to `Config/AllowedDomains.swift`:

```swift
static let trusted: Set<String> = [
    "www.axionx.com.au",
    "axionx.com.au",
    "your-project.replit.app",  // dev only
]
```

### 2. Set Signing

- Select the `AxionX` target → **Signing & Capabilities**
- Set your Apple Developer **Team**
- Bundle ID is pre-set to `com.axionx.ios` — update if needed

### 3. Add App Icon Images

Drop PNG files into `AxionX/Assets.xcassets/AppIcon.appiconset/`.
The `Contents.json` is already wired up. Required sizes:

| File                  | Size (px)   |
|-----------------------|-------------|
| AppIcon-20@2x.png     | 40 × 40     |
| AppIcon-20@3x.png     | 60 × 60     |
| AppIcon-29@2x.png     | 58 × 58     |
| AppIcon-29@3x.png     | 87 × 87     |
| AppIcon-40@2x.png     | 80 × 80     |
| AppIcon-40@3x.png     | 120 × 120   |
| AppIcon-60@2x.png     | 120 × 120   |
| AppIcon-60@3x.png     | 180 × 180   |
| AppIcon-1024.png      | 1024 × 1024 |

**Quick way:** paste your master 1024×1024 into [appicon.co](https://appicon.co) → download all iPhone sizes.

---

## Project Structure

```
ios/
├── AxionX.xcodeproj/                  Xcode project file + shared scheme
└── AxionX/
    ├── AxionXApp.swift                @main SwiftUI entry point + AppDelegate adaptor
    ├── ContentView.swift              Root view: splash → connectivity check → WebView
    │
    ├── Config/
    │   ├── AppConfig.swift            Debug/Release URL, entry path, splash delay
    │   └── AllowedDomains.swift       Trusted hosts, native scheme routing rules
    │
    ├── WebView/
    │   ├── AxionWebView.swift         UIViewRepresentable WKWebView + WebViewStore
    │   ├── WebViewContainer.swift     SwiftUI view hosting WebView + offline overlay
    │   └── WebViewNavigationDelegate.swift  WKNavigationDelegate + WKUIDelegate
    │
    ├── Views/
    │   ├── SplashView.swift           White splash with AxionX branding
    │   └── OfflineView.swift          "No connection" retry screen
    │
    ├── Services/
    │   ├── ConnectivityMonitor.swift  NWPathMonitor @ObservableObject
    │   └── LocationPermissionHelper.swift  CLLocationManager (WhenInUse only)
    │
    ├── Assets.xcassets/               AppIcon + AccentColor (#2563EB) + LaunchLogo
    ├── LaunchScreen.storyboard        OS-level splash before SwiftUI boots
    └── Info.plist                     Permissions, ATS, portrait-only, light mode
```

---

## How It Works

### App Launch Sequence

```
OS Launch
  └── LaunchScreen.storyboard  (white + AxionX title — before SwiftUI starts)
        └── AxionXApp (@main)
              └── ContentView
                    ├── SplashView  (1.4 s)
                    └── WebViewContainer
                          └── AxionWebView  →  loads AppConfig.entryURL
```

### URL Routing

| URL type                              | Behaviour              |
|---------------------------------------|------------------------|
| `*.axionx.com.au/m/*`                 | Stays in WebView       |
| Any trusted host in `AllowedDomains`  | Stays in WebView       |
| `maps.apple.com` / `maps.google.com`  | Opens Apple Maps       |
| `tel:`, `sms:`, `facetime:`           | Opens native system app|
| Any other `https://` URL              | Opens in Safari        |

### Session Persistence

WKWebView uses `.default()` persistent data store — cookies survive app restarts naturally. If the Flask session expires, the server redirects to `/m/login` and the user logs in again. No separate native auth layer needed.

### Offline Handling

`ConnectivityMonitor` watches the network path. If the initial connection check fails, `ContentView` shows `OfflineView`. After the WebView loads, `WebViewNavigationDelegate` handles navigation errors and toggles the `OfflineView` overlay in `WebViewContainer`.

---

## Build Configurations

| Config  | URL                                           |
|---------|-----------------------------------------------|
| Debug   | `debugBaseURL` from `AppConfig.swift`         |
| Release | `https://www.axionx.com.au` (production)      |

---

## Archive for TestFlight

1. Select **Any iOS Device (arm64)** as build target
2. **Product → Archive**
3. In Organizer → **Distribute App → TestFlight & App Store**
4. Xcode handles code signing automatically with your Team set

See `TESTFLIGHT_NOTES.md` for the 12-step tester guide.

---

## Future Expansions (v2+)

- **Push notifications** — stub is in `AxionAppDelegate` (`AxionXApp.swift`), just uncomment
- **Background GPS** — `LocationPermissionHelper` is ready for `.authorizedAlways` upgrade
- **Biometric unlock** — add `LAContext.evaluatePolicy()` in `SceneDelegate`-equivalent
- **Native file/camera upload** — add `UIImagePickerController` or `PHPickerViewController`
- **SwiftUI screen replacement** — swap individual web routes with native SwiftUI views by intercepting those URL patterns in `WebViewNavigationDelegate`
