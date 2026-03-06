# AxionX iOS Wrapper

Native iPhone wrapper for the AxionX mobile web platform. Opens the AxionX `/m/*` routes
in a WKWebView with native session persistence, URL routing, location permission handling,
and offline error recovery.

---

## Getting Started

### Requirements
- Mac with Xcode 15 or later
- Apple Developer account (for device testing and TestFlight)
- iOS 16+ test device or simulator

### Open the project

```bash
# From the repo root
open ios/AxionX.xcodeproj
```

### Configure the dev URL

1. Open `AxionX/Config.swift`
2. Replace `YOUR-REPLIT-DEV-URL` with your Replit project URL:
   ```swift
   static let startURL = URL(string: "https://your-project.replit.app/m/login")!
   ```
3. Also add your Replit host to `allowedHosts`:
   ```swift
   static let allowedHosts: Set<String> = [
       "www.axionx.com.au",
       "your-project.replit.app",  // dev only
   ]
   ```

### Configure signing

1. Select the `AxionX` target in Xcode
2. Under **Signing & Capabilities**, set your Development Team
3. The bundle identifier is pre-set to `au.com.axionx.app` — change if needed

### Run on device or simulator

- Select your target device from the scheme menu
- Press ▶ (Cmd+R) to build and run

---

## Project Structure

```
ios/
├── AxionX.xcodeproj/           Xcode project file
│   ├── project.pbxproj         Build system configuration
│   └── xcshareddata/
│       └── xcschemes/
│           └── AxionX.xcscheme Shared run/archive scheme
├── AxionX/
│   ├── AppDelegate.swift       App lifecycle + push notification readiness (stubbed)
│   ├── SceneDelegate.swift     Window setup, foreground resume logic
│   ├── WebViewController.swift Main WKWebView controller, URL routing, link handling
│   ├── OfflineViewController.swift  "No connection" screen with Retry button
│   ├── LocationPermissionManager.swift  CLLocationManager wrapper for GPS permission
│   ├── Config.swift            Build-time URL selection (Debug vs Release)
│   ├── Info.plist              App permissions, capabilities, scene config
│   ├── LaunchScreen.storyboard White splash with AxionX branding
│   └── Assets.xcassets/
│       ├── AppIcon.appiconset/ App icon (add PNG files — see below)
│       ├── AccentColor.colorset  Brand blue #2563EB
│       └── LaunchLogo.imageset  Wordmark for splash (add PNG files)
├── TESTFLIGHT_NOTES.md         Internal tester guide
└── README.md                   This file
```

---

## App Icon Assets Required

The `Assets.xcassets/AppIcon.appiconset/Contents.json` is configured and ready.
You need to provide the PNG icon files. Required sizes:

| Filename              | Size (px)  | Use                    |
|-----------------------|------------|------------------------|
| AppIcon-20@2x.png     | 40 × 40    | Notifications @2x      |
| AppIcon-20@3x.png     | 60 × 60    | Notifications @3x      |
| AppIcon-29@2x.png     | 58 × 58    | Settings @2x           |
| AppIcon-29@3x.png     | 87 × 87    | Settings @3x           |
| AppIcon-40@2x.png     | 80 × 80    | Spotlight @2x          |
| AppIcon-40@3x.png     | 120 × 120  | Spotlight @3x          |
| AppIcon-60@2x.png     | 120 × 120  | Home screen @2x        |
| AppIcon-60@3x.png     | 180 × 180  | Home screen @3x        |
| AppIcon-1024.png      | 1024 × 1024 | App Store / TestFlight |

Place all PNG files in `AxionX/Assets.xcassets/AppIcon.appiconset/`.

**Tip:** Use a tool like [AppIconGenerator](https://appicon.co/) — paste your 1024×1024
master icon and download all sizes at once.

---

## Build Configurations

| Config  | URL loaded                                      |
|---------|-------------------------------------------------|
| Debug   | `YOUR-REPLIT-DEV-URL.replit.app/m/login`        |
| Release | `https://www.axionx.com.au/m/login` (production)|

Edit `Config.swift` to change URLs.

---

## Archive and TestFlight Upload

1. Select **Any iOS Device (arm64)** as the build target
2. Menu: **Product → Archive**
3. When the Organizer opens, click **Distribute App**
4. Choose **TestFlight & App Store**
5. Follow prompts — Xcode will handle code signing automatically

---

## URL Routing Rules

| URL type                          | Behaviour              |
|-----------------------------------|------------------------|
| `*.axionx.com.au/m/*`             | Stays in WebView       |
| `*.axionx.com.au` (other paths)   | Stays in WebView       |
| `maps.apple.com` / `maps.google.com` | Opens Apple Maps    |
| `tel:`, `sms:`, `facetime:`       | Opens native app       |
| Any other `https://` URL          | Opens in Safari        |

---

## Future Native Features (v2+)

- Push notifications (APNs token registration already stubbed in `AppDelegate.swift`)
- Background GPS tracking via `CLLocationManager` always-on mode
- Biometric unlock (Face ID / Touch ID) for session resume
- Native camera / photo upload for job updates
- Native file download handling
- Gradual SwiftUI screen replacement for key workflows
