---
name: android
description: Build, test and verify native Android apps entirely from the CLI — no Android Studio. Kotlin, Jetpack Compose, Gradle version catalogs, and a headless-emulator self-verification loop (boot AVD with KVM, install APK, drive the UI over adb, screenshot and read the result). Use when creating an Android project from scratch, adding Gradle modules, choosing AGP/Kotlin/Compose versions, fixing Android or Compose build errors, running or smoke-testing an app on an emulator from the terminal, driving UI via adb (screencap, input tap/swipe), triaging crashes from logcat, or verifying an Android change actually works without an IDE. Covers SDK bootstrap via sdkmanager/avdmanager, Gradle wrapper bootstrap when gradle isn't installed, known-good version sets, pure-Kotlin core modules for fast JVM tests, and dependency-probing Maven Central before trusting an artifact exists.
---

# Android from the CLI

Everything here works on a headless Linux box with no Android Studio. Two principles drive the structure: **keep domain logic in a pure-Kotlin module so tests run on the JVM in seconds**, and **prove the app works by booting it, driving it, and looking at screenshots** — compiling is not verification.

## SDK + toolchain bootstrap

Check what exists before installing anything:

```bash
ls ~/Android/Sdk/{platforms,build-tools,cmdline-tools,platform-tools} 2>/dev/null
java -version   # need JDK 17+; 21 is fine
which gradle    # usually absent — see wrapper bootstrap below
```

Missing pieces via `sdkmanager` (licenses first, non-interactive):

```bash
SDKM=~/Android/Sdk/cmdline-tools/latest/bin/sdkmanager
yes | $SDKM --licenses > /dev/null
$SDKM "platform-tools" "platforms;android-36" "build-tools;36.0.0"
```

`local.properties` (gitignored): `sdk.dir=/home/<user>/Android/Sdk`.

**Gradle wrapper bootstrap when `gradle` isn't installed**: download a distro zip once to a scratch dir, use it to generate the committed wrapper, then forget it:

```bash
curl -sLo gradle.zip https://services.gradle.org/distributions/gradle-8.11.1-bin.zip && unzip -q gradle.zip
./gradle-8.11.1/bin/gradle wrapper --gradle-version 8.11.1   # run in the project dir
```

**Trap**: a global gitignore with `*.jar` silently drops `gradle/wrapper/gradle-wrapper.jar` from commits — check `git check-ignore -v gradle/wrapper/gradle-wrapper.jar` and `git add -f` it. A repo whose `./gradlew` fails for everyone else is the symptom.

## Versions: pick a known-good set, don't chase latest

Latest-everything is how Android builds break. Rules:

- Choose an AGP/Kotlin/Compose-BOM trio you know coexists; upgrade deliberately, one axis at a time. A safe conservative set: AGP 8.7.x · Kotlin 2.0.x + `org.jetbrains.kotlin.plugin.compose` (mandatory since Kotlin 2.0 — Compose without this plugin fails cryptically) · Compose BOM current-ish · Gradle 8.11.x.
- If only a newer platform is installed (e.g. `android-36` with an older AGP), set `android.suppressUnsupportedCompileSdk=36` in `gradle.properties` instead of downloading an older platform.
- **Probe Maven Central before trusting an artifact exists** — model memory invents versions:

```bash
curl -s https://repo1.maven.org/maven2/<group-path>/<artifact>/maven-metadata.xml | grep -oE '<latest>[^<]+'
```

- For an unfamiliar library's real API, don't guess from memory — pull its `-sources.jar` from Maven Central, unzip, and grep the actual signatures.

## Project skeleton

- One version catalog (`gradle/libs.versions.toml`); modules: `:app` (Android, thin) + `:core` (pure `org.jetbrains.kotlin.jvm`, zero Android deps).
- **Everything that can live in `:core` lives in `:core`**: codecs, state machines, policies, domain models. Inject time (`nowMs: Long` parameters, never `System.currentTimeMillis()` inside logic) so tests are deterministic and simulation harnesses are possible. `:core` tests run in seconds with no emulator; that's where the real coverage goes.
- `settings.gradle.kts`: `pluginManagement` repos google (with `includeGroupByRegex` filters) + mavenCentral + gradlePluginPortal; `dependencyResolutionManagement` google + mavenCentral, `FAIL_ON_PROJECT_REPOS`.
- Minimal launcher icon without Studio assets: `mipmap-anydpi-v26/ic_launcher.xml` adaptive icon referencing two vector drawables (bg + fg). minSdk 26 makes anydpi-v26 the only variant needed.
- Skip AppCompat for Compose-only apps: activity theme `@android:style/Theme.Material.Light.NoActionBar`, `ComponentActivity` + `setContent`.

## Headless emulator verification loop

The high-value trick almost nobody documents. Requires `/dev/kvm` (check: `ls -la /dev/kvm`).

```bash
SDKM=~/Android/Sdk/cmdline-tools/latest/bin/sdkmanager
$SDKM "emulator" "system-images;android-36;google_apis;x86_64"        # ~2 GB once
echo no | ~/Android/Sdk/cmdline-tools/latest/bin/avdmanager create avd \
  -n test -k "system-images;android-36;google_apis;x86_64" -d pixel_7
~/Android/Sdk/emulator/emulator -avd test -no-window -gpu swiftshader_indirect \
  -no-audio -no-boot-anim -no-snapshot &                               # backgrounded
adb wait-for-device
until [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" = "1" ]; do sleep 5; done
```

Then the verify cycle:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n <applicationId>/.MainActivity
sleep 15                                          # let it actually run before judging
adb shell "logcat -d | grep -E 'FATAL EXCEPTION|AndroidRuntime.*<applicationId>'"
adb shell pidof <applicationId>                   # still alive = didn't crash silently
adb exec-out screencap -p > shot.png              # LOOK at it — read the image
adb emu kill                                      # free the RAM when done
```

- `swiftshader_indirect` renders GL in software — MapLibre/Canvas/Compose all work with no GPU.
- Judge behavior over time: screenshot, wait for the app's own dynamics (timers, animations, data arriving), screenshot again, compare.
- A clean install + alive pid + zero FATAL lines + a screenshot that shows the expected UI is the minimum bar for claiming "it works".

## Driving the UI over adb

```bash
adb shell input tap X Y            # coordinates in PHYSICAL pixels
adb shell input swipe X1 Y1 X2 Y2 300
adb shell input text "hello" ; adb shell input keyevent 66   # type + enter
```

If a screenshot viewer reports a scaled size (e.g. displayed 900×2000 for a 1080×2400 device), multiply measured coordinates by the scale factor before tapping. For stable targeting across devices, `adb shell uiautomator dump` gives an XML of bounds per node.

Crash triage: `adb shell "logcat -d --pid $(adb shell pidof <appId>)"` for just the app; `logcat -c` to reset between attempts; `-d` dumps and exits (never stream interactively in an agent loop).

## Compose gotchas (cost real build time)

- `Modifier.weight(...)` is a **scope member** of Row/Column — importing `androidx.compose.foundation.layout.weight` is a compile error ("internal in file"); delete the import, keep the call.
- Kotlin ≥2.0 requires the `org.jetbrains.kotlin.plugin.compose` Gradle plugin; `buildFeatures { compose = true }` alone worked only on Kotlin 1.x.
- Wrap platform views (MapView etc.) in `AndroidView` + `DisposableEffect` forwarding lifecycle (`onStart/onResume` … `onDestroy`); skipping lifecycle forwarding leaks or blanks the view.
- `collectAsStateWithLifecycle()` needs `androidx.lifecycle:lifecycle-runtime-compose`, not the plain runtime artifact.

## House conventions

- Makefile as entry point: `make start` (assemble + `adb install -r` + `am start`), `make test` (JVM tests), `make tmux` / `make tmux-new-session`. Use `echo -e` for colored output.
- Client-facing UI ships i18n from day one: `values/`, `values-es/`, `values-ca/` — sentence case for es/ca strings.
- Wire formats / persisted enum codes: stable integer codes in the enum (`FLAT(0)`), decode unknowns to null/ignore, never renumber — document "append only" at the definition site.
