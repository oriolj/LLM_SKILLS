---
name: capacitor-ios
description: Compile, run, and distribute a Capacitor iOS app from the CLI — simulator builds, direct-to-device installs, TestFlight archive/upload, App Store submission. Use for any Capacitor/Ionic iOS build/signing/distribution task ("build for iOS", "install on my iPhone", "upload to TestFlight", "why won't it sign", "errSecInternalComponent", "no devices to generate a provisioning profile"). Encodes the disposable-ios/ convention (never park config in the generated project), signing-at-build-time via xcodebuild flags, keychain/codesign failure diagnosis, and the archive→upload lane with -allowProvisioningUpdates.
---

# Capacitor iOS: compile & distribute

Everything runs from the web project root on a Mac with **full Xcode**
(Command Line Tools alone cannot build iOS). If the project has Makefile
lanes (e.g. `make ios-sync` / `ios-build`), prefer them; the raw commands
below are what such lanes wrap.

## Ground rules (violating these is the #1 failure mode)

1. **Treat `ios/` as git-ignored and disposable.** `npx cap add ios`
   regenerates it; anything hand-edited in Xcode or `ios/` dies on regen.
   Durable config lives OUTSIDE it:
   - An idempotent **config script** (pattern: `scripts/ios-config.sh`, run
     after every `cap sync`) that patches Info.plist keys (usage strings,
     orientation lock) and entitlements/pbxproj additions. Add future plist
     keys there, never in Xcode.
   - `capacitor.config.ts` — the bundle ID's single source of truth.
     Changing it requires regenerating `ios/` (`rm -rf ios && npx cap add
     ios`); `cap sync` does NOT rewrite it.
   - Icon/splash source image + a `capacitor-assets` step per sync (uploads
     are rejected without a real 1024 px icon).
   - **Signing (team, versions) is passed on the `xcodebuild` command line
     at build time** — never stored in the pbxproj.
2. **SPM, not CocoaPods.** Capacitor ≥6 generates an SPM project
   (`ios/App/CapApp-SPM`). Any guide saying `pod install` is for Capacitor ≤5.
3. Keep a per-project living log (e.g. `docs/IOS.md`) of signing status and
   follow-ups; read it before promising a capability in a build.

## Compile (no signing, no Apple account needed)

```bash
npm run build && npx cap sync ios        # + config script + assets
xcodebuild -project ios/App/App.xcodeproj -scheme App \
  -destination 'platform=iOS Simulator,name=iPhone 17' build
```

If a simulator build fails right after `ios/` was regenerated, re-run the
sync so the config script patches the fresh project at least once.

### Native-extension gotchas (widgets / App Intents)

- **`AppShortcuts.xcstrings` requires a 17.0+ deployment target.** The Siri
  phrase-catalog format hard-fails `ValidateAppShortcutStringsMetadata`
  ("only supported for iOS 17.0 and above") when the app targets lower —
  regular string catalogs (`Localizable.xcstrings`) back-deploy fine, only
  the AppShortcuts one is restricted. The back-deploy path is the legacy
  variant-group format: per-locale `xx.lproj/AppShortcuts.strings` files
  (keys = the English phrases in the `AppShortcutsProvider` Swift source),
  registered as a `PBXVariantGroup`. Xcode keys phrase-catalog semantics to
  the exact basename, so guard against the file's reintroduction by name.
- **A pbxproj reconciler script must prune, not just add.** `ios/` persists
  between syncs; a find-or-create-only script leaves dangling references
  after a source file is deleted/renamed ("Build input file cannot be found"
  until a manual regen). Symmetric rule: remove refs whose resolved on-disk
  path is gone before the add globs run.

## Simulator verification (what's automatable headlessly)

`xcrun simctl boot/install/launch` + `simctl io booted screenshot` cover
launch smoke tests. Limits worth knowing before promising more:

- **Custom-scheme deep links can't be end-to-end tested headlessly.**
  `simctl openurl booted "myapp://…"` always counts as an external open, so
  iOS shows an "Open in <app>?" dialog — and clicking it via AppleScript
  needs the macOS Accessibility permission (System Events times out with
  -1712 without it; `simctl spawn booted uiopen` doesn't exist). Scheme
  *resolution* (the dialog naming the app) is the automatable evidence;
  the post-tap routing needs a human or XCUITest.
- App Intents presence is verifiable statically: `Metadata.appintents/` in
  the built .app, and the `.appex` under `PlugIns/`, prove
  extraction/embedding without running Siri.

## Signing preconditions (check before any device/TestFlight work)

```bash
security find-identity -v -p codesigning
```

- `Apple Development: … ` → can build to a plugged-in device.
- `Apple Distribution: … (TEAMID)` → can archive for TestFlight/App Store.
- **0 identities / only "(Personal Team)" in Xcode → the paid Developer
  Program membership isn't active yet.** Distribution certs can't exist on
  free teams; the user must wait for the "Welcome to the Apple Developer
  Program" email (payment processing, up to 48 h).
- The `(TEAMID)` suffix on an **Apple Distribution** identity is the
  `DEVELOPMENT_TEAM` value used below. (The suffix on an "Apple Development"
  identity is NOT a team ID — those certs are account-wide since Xcode 11.)
  With multiple teams, the paid team is the one on the Distribution identity.
- **Certs listed but "0 valid identities"** (`find-identity` without `-v`
  shows them, with `-v` shows none): the Apple **WWDR intermediate** is
  missing, so the chain can't validate. Fix:
  ```bash
  curl -sO https://www.apple.com/certificateauthority/AppleWWDRCAG3.cer
  security import AppleWWDRCAG3.cer -k ~/Library/Keychains/login.keychain-db
  ```
  (Match the intermediate to the cert's issuer `OU=` if in doubt:
  `security find-certificate -c "Apple Distribution" -p | openssl x509 -noout -issuer`.)
- **`errSecInternalComponent` on CodeSign steps** (compile succeeds, then
  embedded frameworks fail to sign): the private key isn't usable from a
  non-GUI shell. TWO fixes, both usually needed (user runs them — they
  prompt for the macOS login password; never put the password in a command):
  ```bash
  # 1. one-time per new cert: let CLI codesign use the keys
  security set-key-partition-list -S apple-tool:,apple:,codesign: -s ~/Library/Keychains/login.keychain-db
  # 2. per session: actually unlock the keychain (#1 alone is NOT enough)
  security unlock-keychain ~/Library/Keychains/login.keychain-db
  ```
  Diagnose with `security show-keychain-info ~/Library/Keychains/login.keychain-db`
  → "User interaction is not allowed" = locked. Verify cheaply before a long
  archive: `cp /bin/ls /tmp/t && codesign -f -s <identity-hash> /tmp/t`. A
  keychain lock-timeout can re-lock mid-archive — archive right after
  unlocking.

Sign-in itself (Xcode → Settings → Accounts) is interactive — the user does
it; you verify with `find-identity`.

## Archive (shared by all distribution lanes)

```bash
npm run build && npx cap sync ios
TEAM_ID=XXXXXXXXXX   # from security find-identity
cd ios/App && xcodebuild -project App.xcodeproj -scheme App \
  -destination 'generic/platform=iOS' \
  -archivePath build/App.xcarchive archive \
  CODE_SIGN_STYLE=Automatic \
  DEVELOPMENT_TEAM=$TEAM_ID \
  MARKETING_VERSION=1.0.0 \
  CURRENT_PROJECT_VERSION=$(git rev-list --count HEAD) \
  -allowProvisioningUpdates
```

- `-allowProvisioningUpdates` registers the bundle ID on the developer
  account and syncs capabilities from the entitlements file — no manual
  portal clicking.
- **Every upload needs a unique, increasing build number.**
  `git rev-list --count HEAD` is a free monotonic source; pass it as
  `CURRENT_PROJECT_VERSION` (never edit it into the disposable pbxproj).
  `MARKETING_VERSION` is the user-facing version — bump per release.
- **"Your team has no devices from which to generate a provisioning
  profile"** → automatic signing signs the *archive* with a development
  profile (distribution signing happens at export), and dev profiles need
  ≥1 registered device. On a brand-new team, register a device UDID
  manually — the deterministic fix:
  1. Phone plugged in + trusted → `xcrun xctrace list devices` prints the
     hardware UDID (`00008130-…`; NOT the devicectl "Identifier" UUID).
  2. User adds it at developer.apple.com/account/resources/devices/add.
  Merely connecting the phone is NOT enough — CLI `-allowProvisioningUpdates`
  archives don't register connected devices, and a device-targeted CLI build
  can fail at "developer disk image could not be mounted" before it ever
  registers anything.

## Distribute — direct to device (fastest test loop, no App Store Connect)

The archive's inner `App.app` is development-signed and directly
installable — no ASC app record, no upload, no processing wait. Prereqs:
device registered on the team (above), Developer Mode ON (Settings →
Privacy & Security), phone connected + trusted.

```bash
xcrun devicectl list devices          # device UUID = first column Identifier
xcrun devicectl device install app --device <UUID> \
  ios/App/build/App.xcarchive/Products/Applications/App.app
```

Sanity check that the embedded profile covers the phone (hardware UDID must
be listed): `security cms -D -i …/App.app/embedded.mobileprovision | plutil
-extract ProvisionedDevices json -o - -`. Dev profiles last 1 year on a paid
team (7 days on free accounts).

## Distribute — TestFlight

One-time prerequisites (user actions, in order): active paid membership;
Distribution cert (Xcode → Accounts → Manage Certificates → + → Apple
Distribution); app record in App Store Connect (**after** the first archive
registers the bundle ID) — the public app name must be unique on the store,
have a fallback ready.

Export/upload with an `exportOptions.plist` kept OUTSIDE `ios/` (e.g.
`scripts/exportOptions.plist`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>method</key><string>app-store-connect</string>
  <key>destination</key><string>upload</string>
  <key>teamID</key><string>XXXXXXXXXX</string>
</dict></plist>
```

```bash
xcodebuild -exportArchive -archivePath build/App.xcarchive \
  -exportOptionsPlist ../../scripts/exportOptions.plist \
  -allowProvisioningUpdates
```

Uses the Xcode signed-in session. If it demands credentials headlessly,
create an App Store Connect API key (ASC → Users and Access → Integrations)
and add `-authenticationKeyPath <key.p8> -authenticationKeyID <KID>
-authenticationKeyIssuerID <ISSUER>`. Fallback when CLI auth misbehaves:
Xcode → Product → Archive → Organizer → Distribute App (GUI).

After upload: processing ~5–30 min (email on completion). Internal testers
(ASC team users) get builds immediately, no review; external testers' first
build needs Beta App Review (~1 day), later builds usually instant. Builds
expire after 90 days. Once the first upload succeeds, wrap archive+upload
into a one-command lane (Makefile target) so releases stay reproducible.

## Distribute — App Store

Same archive/upload lane; the rest is ASC metadata work. Common rejection
traps to check before submitting: **in-app account deletion** is required if
the app has accounts; **Sign in with Apple is required when other social
sign-ins (Google) are present**; privacy questionnaire must match what the
app actually collects.

## Known gotchas

- Capabilities (HealthKit, push, sign-in) need both the entitlements file
  (maintained by the config script) and the App ID capability — the latter
  syncs automatically via `-allowProvisioningUpdates`.
- Don't promise plugin capabilities (APNs, Google/Apple sign-in URL schemes)
  in a build before their per-platform setup is done — track the follow-ups
  in the project's iOS doc.
- **App Groups are the exception to "capabilities sync automatically"**
  (Panotxa watch targets, 2026-09-21). `-allowProvisioningUpdates` creates
  the App ID and turns the App Groups capability ON, but never *assigns* a
  group to it, so the profile lacks `com.apple.security.application-groups`
  and the archive fails with `Provisioning profile "iOS Team Provisioning
  Profile: <bundle>" doesn't match the entitlements file's value for the
  com.apple.security.application-groups entitlement`. Fix in the portal
  (Identifiers → the App ID → App Groups → Configure → tick the group →
  Save → Confirm — "will invalidate provisioning profiles" is expected) and
  re-archive; it can be driven in the browser, it is only clicks. Every new
  extension target that shares the group (widget, watch app, watch widgets)
  needs this once.
- **SPM floors (`from:`) in plugin packages re-resolve to the newest release
  on every `ios/` regen.** A working lane breaks the day a dependency ships a
  breaking minor: `@sentry/capacitor` 4.2.0 declared `sentry-cocoa from:
  "9.16.1"`, sentry-cocoa 9.29.0 (2026-09-18) moved `PrivateSentrySDKOnly`
  behind `@_spi(Private)`, and the archive failed with `cannot find
  'PrivateSentrySDKOnly' in scope`. Check upstream first — the plugin's next
  release usually pins (`exact: "9.28.0"` in 4.4.0); mirror that pin with a
  patch-package patch on `node_modules/<plugin>/Package.swift` when the
  upgrade drags in peer bumps you don't want in a release build. After
  changing a pin, **wipe the DerivedData** (`~/Library/Developer/Xcode/
  DerivedData/<Scheme>-*`) — the precompiled module of the old version is
  reused and the same error persists although `Package.resolved` and the
  downloaded xcframework are already the new version.
- **Reproduce compile errors without the keychain**: an unsigned simulator
  build of the regenerated project (`xcodebuild … -destination
  'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build` into a
  scratch `-derivedDataPath`) surfaces the same Swift errors as the archive
  and needs no signing identity.
- **The keychain unlock does not cross the agent's sandbox.** An unlock done
  in the user's terminal leaves the agent's shell still failing the codesign
  probe with `errSecInternalComponent`; the archive/upload then runs from the
  user's terminal (the lane prompts for the password on a tty) while the
  agent handles portal + App Store Connect in the browser. The keychain also
  re-locks on its inactivity timeout — unlock right before the lane.
- **App Store Connect testers, quirks**: a tester added by email shows a red
  "No Builds Available" until a build is (re)added to their group — adding a
  tester to a group that already has an approved build does *not* invite them
  to it by itself. Their email address in the list is a `mailto:` link; a
  click opens the user's mail client — select the row checkbox instead.
- If releases become routine/CI-driven, consider fastlane (match/beta);
  until then plain `xcodebuild` keeps the surface small.
