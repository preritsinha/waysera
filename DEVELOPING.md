# Developing Waysera

Everything a contributor needs. The [README](README.md) is for people who just
want to use the app.

---

## Project structure

Two independent projects share this repository. They are not coupled: neither
reads the other's files, and each builds and runs on its own.

```
waysera/
├── web/                     # Project 1 — the web app and its relay
│   ├── frontend/            # Client. No build step. This alone is served.
│   │   ├── index.html
│   │   ├── replay.html
│   │   ├── tests.html       # Browser test runner
│   │   └── assets/
│   │       ├── crypto.js    # AES-GCM, ECDH handoff, invite links
│   │       ├── journey.js   # Relay session and protocol
│   │       ├── store.js     # IndexedDB
│   │       ├── validate.js  # Peer input validation
│   │       ├── search.js    # Photon geocoding, tiered by distance
│   │       ├── export.js    # JSON and GPX
│   │       ├── replay.js    # Playback
│   │       ├── polish.js    # Skeletons, sheet physics
│   │       ├── index.js     # App
│   │       └── app-mobile.css
│   │
│   ├── backend/             # The relay. It stores nothing.
│   │   ├── main.py          # Health check + WebSocket relay
│   │   ├── services/relay.py
│   │   ├── render.yaml      # Deploy blueprint (rootDir: web/backend)
│   │   └── tests/           # pytest
│   │
│   ├── tools/               # Five test harnesses
│   ├── start.sh
│   └── stop.sh
│
├── android_app/             # Project 2 — the Android app (Capacitor)
│   ├── www/                 # Its own copy of the client. Edit directly.
│   │   └── assets/
│   │       ├── android-location.js   # Foreground-service GPS
│   │       ├── polish.js             # Haptics, skeletons, sheet physics
│   │       └── config.js             # RELAY_URL, PUBLIC_ORIGIN
│   ├── android/             # Generated native project
│   │   └── app/src/
│   │       ├── main/AndroidManifest.xml
│   │       ├── main/res/    # Adaptive launcher icon (vector)
│   │       └── debug/       # Cleartext exemption, debug builds only
│   ├── capacitor.config.json
│   └── build-apk.sh
│
├── BRAND.md                 # Brand source of truth
└── README.md
```

`frontend/` is a subdirectory rather than the project root on purpose: the dev
server serves that directory and nothing above it, so `backend/` source and any
real `.env` cannot be fetched over HTTP.

`android_app/www/` is a genuine copy, not a build artefact — the two clients are
free to diverge as the app grows native behaviour. The cost is that a fix in one
does not reach the other. In practice they differ by about 24 lines: the Android
copy mints invite links from `PUBLIC_ORIGIN` rather than `window.location.origin`
(inside a WebView the origin is `http://localhost`), and it loads Leaflet and the
marker images from `assets/vendor/` so the app starts without a network round
trip.

### What the Android app adds

Wrapping the web app in Capacitor buys exactly one thing that a browser cannot
do, and it is the reason the wrapper exists:

**Background location.** A browser suspends geolocation the moment its tab is
hidden — which is precisely when a group most needs to see each other move.
Android only permits indefinite location access from a *foreground service*, and
such a service must show a permanent notification. That notification is not
optional and cannot be hidden.

Everything else is polish: haptics, an adaptive launcher icon, and bundled
assets. The map, routing, search, crypto and relay protocol are the same code.

---

## The relay API

Two endpoints. That is the whole surface.

```http
GET /v1/health
```

```
WS /v1/relay/{channel_id}
```

`channel_id` is the lowercase SHA-256 of a journey code, worked out on the client, so the code itself never reaches the server. Anything that is not a 64-character hex digest is refused.

Every frame received is forwarded verbatim to the channel's other sockets and to nobody else. The sender never receives its own frames back. The relay never parses, logs, or retains a payload.

Limits: 64 KB per frame, 20 messages per second per socket, 10 sockets per channel.

---

## Tests

```bash
cd web

# Relay
(cd backend && .venv/bin/python -m pytest)

# Crypto, storage, validation, session, export, replay — runs in real Chrome
backend/.venv/bin/python tools/run_browser_tests.py

# Loads the actual page and drives a journey creation
backend/.venv/bin/python tools/smoke_app.py

# Two headless browsers and a live relay, end to end
backend/.venv/bin/python tools/integration_test.py
```

The browser suites run in Chrome rather than Node for a reason. The code under test needs WebCrypto **and** IndexedDB, and IndexedDB has no faithful Node equivalent, so a polyfill would end up testing the polyfill.

The integration test also asserts the property everything else rests on. It joins a live journey as an unauthorised third party and checks that what crosses the wire is unreadable.

---

## Deploying

**Relay** — a Render web service, root directory `web/backend`, start command:

```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Set `ALLOWED_ORIGINS` to your frontend origin. Note that WebSocket upgrades are not subject to CORS, and the relay uses no cookies or credentials, so this only covers the health check.

**Web client** — a Render static site, root directory `web/frontend`, publish directory `.`.

Map tiles come from Stadia Maps (`osm_bright`, `alidade_smooth_dark` at night).

Stadia serves unauthenticated requests when the referer is `localhost`, which
covers local development and the Android app — a Capacitor WebView reports
`http://localhost`. **That allowance is for development only.** A released build
must set `STADIA_KEY` in `assets/config.js` or tiles will 401 for every user.

CARTO was used previously and was dropped: it began watermarking unauthenticated
tiles, and a free key obtained from their site never authenticated — verified
against several parameter names, both hostnames, fresh cache misses and a
matching referer.

---

## Building and installing the Android app

### Prerequisites

```bash
brew install node openjdk@21
brew install --cask android-commandlinetools

export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses
"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" \
    "platform-tools" "platforms;android-36" "build-tools;36.0.0"
```

JDK **21** and SDK **36** specifically — Capacitor 8 rejects 17 and 35, and
`build-apk.sh` pins both so a shell with a different default JDK still works.

### Configure before building

`android_app/www/assets/config.js` has two values, and an APK built without them
installs and opens but can never reach another person:

| Value | What breaks if it is empty or wrong |
| --- | --- |
| `RELAY_URL` | No group. Everything else — map, search, routing, your own position — still works. |
| `PUBLIC_ORIGIN` | Invite links point at `localhost` and open for nobody. Joining by six-character code still works. |

`RELAY_URL` must be reachable **from the phone**. `localhost` means the phone
itself. Use `http://10.0.2.2:8000` for the Android emulator, which is its alias
for your machine's loopback, and a public `https://` URL for a real device.

### Build

```bash
cd android_app
npm install          # first time only
./build-apk.sh
```

The APK lands at
`android_app/android/app/build/outputs/apk/debug/app-debug.apk` (~9 MB).

### Install on a device over USB

Enable **Developer options** (Settings → About phone → tap *Build number* seven
times), then **USB debugging**. Plug the phone in and accept the prompt.

```bash
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
$ANDROID_HOME/platform-tools/adb devices        # confirm it is listed
$ANDROID_HOME/platform-tools/adb install -r \
    android_app/android/app/build/outputs/apk/debug/app-debug.apk
```

### Install on an emulator

```bash
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
export JAVA_HOME="$(brew --prefix openjdk@21)"

"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" \
    "emulator" "system-images;android-35;google_apis;arm64-v8a"
"$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager" create avd \
    -n waysera -k "system-images;android-35;google_apis;arm64-v8a" -d pixel_7

"$ANDROID_HOME/emulator/emulator" -avd waysera &
$ANDROID_HOME/platform-tools/adb install -r \
    android_app/android/app/build/outputs/apk/debug/app-debug.apk

# Fake a position (longitude first)
$ANDROID_HOME/platform-tools/adb emu geo fix 77.5946 12.9716
```

Two emulators are worth the trouble: this is a group app, and one device shows a
map with a single dot on it. `avdmanager` a second AVD and start it with
`-port 5556`.

---

## Distributing the Android app

**Yes — Android permits it, unlike iOS.** A user downloads the `.apk`, taps it,
and grants "Install unknown apps" to whatever app they downloaded it with. No
store, no account, no developer fee. Expect Play Protect to warn about an
unrecognised developer; that warning is normal for sideloaded apps and is
dismissible.

**But the APK this repository currently builds is not fit to hand out**, for two
independent reasons:

1. **It is a debug build.** `android/app/build.gradle` declares a `release`
   block with no `signingConfig`, so `assembleRelease` would emit an *unsigned*
   APK that Android refuses to install outright. Only `assembleDebug` works
   today, and it signs with the shared Android debug keystore — which every
   developer's machine also has.

2. **`RELAY_URL` points at `10.0.2.2`**, the emulator's alias for the build
   machine. On a real phone that address is meaningless, so the app opens and
   the group stays permanently empty.

There is also a trap worth knowing before you share anything: **a debug-signed
install cannot be upgraded by a release-signed one.** The signatures differ, so
every early tester has to uninstall and lose their local journeys when you
switch. Set up release signing *before* the first APK leaves your machine.

### To make a distributable build

```bash
keytool -genkey -v -keystore waysera-release.jks \
    -keyalg RSA -keysize 2048 -validity 10000 -alias waysera
```

Keep that file and its passwords out of the repository — losing them means you
can never ship an update to anyone who installed the old build. Then add a
`signingConfig` to the `release` block in `android_app/android/app/build.gradle`,
set the two config values above to real public URLs, and build with
`./gradlew assembleRelease`.

For more than a handful of testers, Google Play internal testing distributes by
link and handles signing, updates and the Play Protect warning for you. It costs
a one-off $25 developer registration.

---

