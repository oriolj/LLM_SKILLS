---
name: tauri
description: Build, test, package and release Tauri 2 desktop apps (Rust core + webview UI) for Windows, Linux and macOS. Covers cross-building the Windows NSIS installer from Linux in Docker (mingw windows-gnu or cargo-xwin + MSVC), a Linux AppImage that runs on older distributions, macOS builds on a Mac over ssh, headless smoke tests (Xvfb + xdotool, Wine for Windows binaries), bundling native DLLs/dylibs (LAME, WebView2Loader), the updater key, signing with signCommand, tray behaviour on GNOME, keyring traps on autologin, and the workspace layout without src-tauri. Use when building or debugging a Tauri app, when the user asks "can we make an exe from Linux", "build the AppImage / dmg / installer", "the AppImage does not run on Ubuntu", "WebView2Loader.dll not found", "makensis fails", "tauri-action can't find src-tauri", "sign the Windows installer", or "test the desktop app headless".
---

# Tauri 2 desktop apps: build, test, release

Field notes from shipping the EnaCast Broadcaster (Tauri 2 shell + Rust core
crate + React UI, Windows/Linux/macOS, 2026-10). Everything here was
verified on that project unless marked otherwise. Reference implementation:
`~/git/EnaCast/EnacastStreamer/broadcaster/` (`cross/`, `RELEASING.md`,
`TESTING.md`, `app/tauri*.conf.json`).

## 1. Layout that keeps the audio/logic testable

- Put the real work in a **plain Rust crate with no Tauri/GUI dependency**
  (`core/`), a thin Tauri shell (`app/`) and the webview UI (`ui/`). A
  headless CLI (`cli/`) over the same core gives automated end-to-end tests,
  a Linux headless mode, and a way to drive a running app (control files in
  the shared data dir).
- **No `src-tauri/` folder.** It works, but then:
  - `npx tauri` must run from the folder that has `package.json`. Use
    `node ui/node_modules/@tauri-apps/cli/tauri.js build` with the working
    directory set to `app/`, or `npm --prefix ui run tauri -- build`.
  - `tauri-apps/tauri-action` assumes `src-tauri` plus `package.json`. Call
    the CLI directly in CI instead.
  - A plain `cargo build` of the app crate needs `ui/dist` to exist
    (`frontendDist`).
- Point the CLI and the app at the **same data dir** (Tauri uses the bundle
  identifier: `~/.local/share/<id>`, `%APPDATA%\<id>`,
  `~/Library/Application Support/<id>`). Otherwise a single-instance lock
  doesn't cover both, and the CLI can't reach the app.
- **Expose nothing to the webview you don't need.** Keep
  `capabilities/default.json` at `core:default` plus your own commands, drive
  plugins from Rust, and use a strict CSP (`script-src 'self'`, `connect-src`
  self + `ipc:` + `http://ipc.localhost`). Return command errors as JSON
  `{code, detail}` strings so the UI can localise per code. Emit codes, never
  English text the UI pattern-matches.

## 2. Linux

- **AppImage glibc rule.** An AppImage runs only on a glibc at least as new
  as the build host's. One built on Arch fails on Ubuntu LTS. Build in
  `ubuntu:22.04` (Docker); that's also the CI base.
  - Container needs: `libwebkit2gtk-4.1-dev libayatana-appindicator3-dev librsvg2-dev`
    plus your native libraries.
  - Set `APPIMAGE_EXTRACT_AND_RUN=1` so the AppImage tooling works without
    FUSE in the container.
  - Run the container `--user $(id -u):$(id -g)`, with `CARGO_HOME`,
    `CARGO_TARGET_DIR` and `HOME` under the repo's gitignored `target/`, or
    root-owned files land in the checkout.
- **Size.** With `bundleMediaFramework: false` the AppImage was 89 MB (it
  embeds webkit2gtk) and the `.deb` 11 MB. GitHub rejects files over 100 MB,
  so plan download hosting before committing installers to a repo.
- **Deb package name.** Tauri derives it from `productName`
  ("EnaCast Broadcaster" became `ena-cast-broadcaster`) and has no setting
  for it. Set `productName` in `tauri.linux.conf.json` to the package name
  you want and keep the human name in a custom `.desktop` (`desktopTemplate`).
- **Tray on GNOME.** Icons show only with the AppIndicator extension, and
  without it the tray still "creates" successfully. Check the session bus for
  a StatusNotifierWatcher before relying on close-to-tray; when it's absent,
  make close minimise instead of hiding, or the app vanishes.
- **Keyring on autologin.** A PC that logs in automatically leaves the GNOME
  login keyring **locked**, so a `keyring`-crate secret is unreadable at
  boot and an unattended app comes up logged out. Keep an authoritative 0600
  file copy on Linux (sync the keyring from it, carrying deletions). Windows'
  Credential Manager and the macOS Keychain unlock with the session.
- **Audio (cpal).** cpal's PulseAudio host is pure Rust and works on PipeWire
  through pipewire-pulse. The native PipeWire host needs libclang at build
  time. The pulseaudio crate logs an ERROR on every normal client drop:
  filter `pulseaudio::client::reactor=off`.

## 3. Windows from Linux

Two routes. Both build **NSIS only**: the MSI needs WiX, which is Windows-only,
so CI on `windows-latest` builds the MSI.

### Route A, verified: mingw (`x86_64-pc-windows-gnu`) in Docker

- Image `rust:1-trixie` + `rustup target add x86_64-pc-windows-gnu` +
  `apt install mingw-w64 nsis`.
- **Use trixie, not bookworm.** Bookworm's NSIS 3.08 fails with
  `!include: could not find: "Win\RestartManager.nsh"`; trixie's NSIS 3.11
  works.
- Build: `tauri build --target x86_64-pc-windows-gnu --config '<json>'`. The
  `--config` JSON is merged with JSON Merge Patch, so `null` deletes a key.
  Use it to swap per-target resources and set `"targets":["nsis"]` and
  `"beforeBuildCommand":""` (build the UI on the host).
- **`WebView2Loader.dll`.** A gnu build links the loader dynamically (MSVC
  links it statically), so the exe needs the DLL beside it. tauri-build
  copies it to `target/<triple>/release/`, and the NSIS bundler packed it
  automatically (checked in the generated `installer.nsi`). Known bug
  (tauri#16162, 2026-09): with Cargo's new build-dir layout (nightly) that
  copy fails; on stable it worked.
- **Native libraries.** Take prebuilt mingw DLLs from the MSYS2 repository:
  download `mingw-w64-x86_64-<pkg>-<ver>-any.pkg.tar.zst` from
  `repo.msys2.org/mingw/mingw64/` and extract it to get `lib*.dll.a` + `bin/*.dll`.
  - The import library decides the DLL name the exe asks for (LAME:
    `libmp3lame-0.dll`, while vcpkg's MSVC DLL is `libmp3lame.dll`), so map
    the bundle resource to that exact name.
  - Check each DLL's own imports with `x86_64-w64-mingw32-objdump -p x.dll | grep "DLL Name"`.
    The MSYS2 LAME needed only KERNEL32/msvcrt.
- **Check the exe's imports** the same way. Expect only system DLLs plus what
  you ship. The gnu exe was 45 MB uncompressed (MSVC builds are smaller); the
  NSIS setup was 9.3 MB.
- **Read-only bind mounts break the build.** tauri-build writes
  `app/gen/schemas`, and it fails if a declared resource file is missing.
  Mount read-write, or copy the tree inside the container.

### Route B, documented by Tauri, not tried here: cargo-xwin + MSVC

`apt install nsis lld llvm clang`, then `cargo install --locked cargo-xwin`,
`rustup target add x86_64-pc-windows-msvc`, and
`tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc`.
- It downloads the MSVC CRT/SDK (Microsoft licence).
- It links WebView2Loader statically and gives a smaller exe.

### Testing a Windows build without Windows

- Run the **headless CLI exe under Wine** in the same container:
  `apt install wine wine64`. The command is `wine` (Debian has no `wine64` on
  PATH). Use `WINEDEBUG=-all` and `--network host` with `--add-host` for
  tailnet names.
- It proved the Windows build's TLS, the DLL loading and the streaming path
  end to end.
- It does NOT cover WebView2, WASAPI capture or the installer: those need a
  real Windows machine or CI.

### Signing

- From a non-Windows host Tauri skips signing ("only supported on Windows
  hosts"). Set `bundle.windows.signCommand` with `%1` as the file:
  - `artifact-signing-cli -e <endpoint> -a <account> -c <profile> -d <name> %1`
    for Azure **Artifact Signing**, formerly Trusted Signing, formerly
    `trusted-signing-cli`;
  - `relic sign --file %1 --key azure --config relic.conf` for Azure Key Vault;
  - or `osslsigncode` / `jsign` with an HSM/PKCS#11 key.
- Since 2024 an EV certificate no longer gives instant SmartScreen
  reputation. OV certificates need hardware-backed keys.
- An unsigned alpha shows "Windows protected your PC". Users click **More info**
  → **Run anyway**; write that into the install docs.

## 4. macOS (verified on a Mac mini over ssh, macOS 27 arm64)

- Tauri apps need macOS to build the `.app`/`.dmg`; there's no Linux
  cross-build. Build on a Mac over ssh:
  - rsync the tree, excluding `target/`, `node_modules`, `dist` and secrets;
  - run `npm ci` there, because the CLI's native binary differs per platform;
  - keep rustup, cargo and the target dir under a folder excluded from
    backups;
  - run `tauri build --target aarch64-apple-darwin`.
- **Watch the Mac's disk.** One release build took about 2 GB of target
  dir, and free space fell to about 1 GB mid-build on a 94%-full Mac.
- **Over ssh, set `CI=true`.** Otherwise the dmg step tries to drive Finder
  via AppleScript and fails with -1712 (it also leaves "allow sshd to control
  Finder" prompts on the Mac's screen).
- **Homebrew dylibs are not distributable.** Homebrew's LAME 4.0 dylib had a
  macOS 26 minimum and linked Homebrew's `libmpg123` by absolute path. Build
  the native library from source with `MACOSX_DEPLOYMENT_TARGET` set to your
  minimum and `-install_name @rpath/lib….dylib`, then:
  - link against it, with the rpath `@executable_path/../Frameworks`;
  - embed it with `bundle.macOS.frameworks`;
  - verify with `otool -L` (no `/opt/homebrew`) and `otool -l` (`minos`).
- **Ad-hoc signing + hardened runtime + an embedded dylib crashes at launch.**
  dyld refuses it because the binaries have "different Team IDs". Add the
  entitlement `com.apple.security.cs.disable-library-validation`.
  Notarization accepts it, and it keeps an LGPL library user-replaceable.
- **Info.plist / entitlements:**
  - `NSMicrophoneUsageDescription` and the entitlement
    `com.apple.security.device.audio-input`.
  - Without microphone permission, Core Audio still opens the input but
    delivers **digital silence**. Check `AVCaptureDevice` authorization
    first, ask once, and surface a coded "permission pending/denied" state
    instead of a silent stream.
  - `NSAppSleepDisabled` and `LSAppNapIsDisabled`.
- **Sleep and App Nap while working:** one `NSProcessInfo`
  `beginActivity(UserInitiated | IdleSystemSleepDisabled)` covers both.
  macOS drops it if the process dies, so nothing can be orphaned the way a
  `caffeinate` child can. Check with `pmset -g assertions`.
- **Menus.** Tauri's default menu lacks an Edit menu (⌘C/⌘V do nothing in
  inputs) and quits on ⌘Q without asking. Build your own menu if quitting
  mid-task matters.
- **Gatekeeper on an ad-hoc, unnotarized app.** `spctl` says "rejected / no
  usable signature". Since macOS 15 Control-click → Open is gone, so users
  must:
  1. open the app and click Done;
  2. go to System Settings → Privacy & Security → **Open Anyway**;
  3. enter the password and confirm.

  Or run `xattr -dr com.apple.quarantine <app>`. Developer ID +
  notarization (Apple Developer account) removes this.
- **Testing over ssh is limited.** `screencapture` fails ("could not create
  image from display") and Accessibility scripting is blocked. Test the CLI
  end to end, drive the app through its own control channel, and leave the
  visual check to a person.
- **Loopback socket buffers.** macOS buffers about 200 KB on loopback, so
  "stalled peer" tests need longer timeouts there than on Linux.

## 5. Headless smoke tests on Linux

- `dbus-run-session -- xvfb-run -n <N> -s "-screen 0 1024x900x24" <app>`, with
  `WEBKIT_DISABLE_DMABUF_RENDERER=1`. Screenshot with
  `DISPLAY=:N import -window root shot.png` and look at it.
- Drive the UI with `xdotool` (`mousemove x y click 1`, `type --delay 25 …`,
  `key Return`). For native `<select>` dropdowns, click then
  `xdotool key End Return`: coordinates shift when banners appear or vanish,
  so re-screenshot before each click.
- `dbus-run-session` gives a fresh bus with **no keyring**. That reproduces
  the locked-keyring autologin case for free, but it also means a token saved
  through the real keyring is invisible there.
- **Never `pkill -f <pattern>`** with a pattern that also appears in your own
  shell command line: it kills the calling shell (exit 144). Keep pid files,
  or use the `[x]pattern` bracket trick with `pgrep`.
- To show the app on the user's real desktop from an ssh/tty session, set
  `XDG_RUNTIME_DIR=/run/user/<uid>`,
  `WAYLAND_DISPLAY=wayland-1` (or the socket name in that dir), `DISPLAY=:0`
  and `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<uid>/bus`.

## 6. Updater

- `tauri signer generate`. Commit only the public key in `plugins.updater.pubkey`.
  Keep the private key outside the repo, backed up: if it's lost, no
  installed app can ever update again. Pass it as `TAURI_SIGNING_PRIVATE_KEY`
  at build time to get `.sig` files.
- On Windows, installing an update exits the app. Never install while the app
  is doing something that must not be interrupted. Hold an atomic
  "maintenance" reservation in the core from install until restart, and
  re-check after the download.
