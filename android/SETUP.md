# VisionOS Android — Setup

## What's real vs. placeholder right now

The app builds and installs as-is (debug-signed, sideloadable), but two
things are placeholders until you swap them in:

### 1. Firebase project (`android/app/google-services.json`)

This repo currently ships a **fake** `google-services.json` with made-up
IDs — just enough for the `google-services` Gradle plugin to not fail the
build. Google Sign-In will fail with a real (if unhelpful) error until you
replace it with a real one:

1. Go to [Firebase Console](https://console.firebase.google.com/) → create
   a project (or use the same one the backend's `FIREBASE_CREDENTIALS_JSON`
   already points at, if one exists — check with whoever set up
   `backend/.env`).
2. Add an Android app with package name **`com.visionos.app`**.
3. Enable **Authentication → Sign-in method → Google**.
4. Download the real `google-services.json` and replace
   `android/app/google-services.json` with it.
5. Rebuild — `default_web_client_id` (used by `LoginScreen.kt`) is
   generated automatically from that file by the `google-services` plugin.

### 2. Backend URL (`android/app/src/main/java/com/visionos/app/ApiClient.kt`)

Points at a Cloud Run URL that was already in the codebase
(`https://visionos-1004956364101.asia-south1.run.app/`) — verify this is
actually your deployed backend before relying on it; if not, update
`BASE_URL` there.

## Building

```bash
cd android
./gradlew assembleDebug          # or: gradle assembleDebug if no wrapper committed
# Output: android/app/build/outputs/apk/debug/app-debug.apk
```

This APK is **debug-signed** (Android's auto-generated debug keystore) —
installable by sideloading (enable "Install unknown apps" for whatever
you use to transfer the file), but not Play Store-ready. For a Play
Store release you'll need your own upload keystore and a
`buildTypes { release { signingConfig = ... } }` block, plus a Play
Console account.

## What "Add Camera" actually does right now

Three connection types (see `AddCameraScreen.kt`):

- **RTMP Push (recommended)** — generates a unique `rtmp://.../live/<key>`
  URL server-side, shown after creation. You enter that in your DVR's
  "Platform Access" / "RTMP" / "Push Stream" menu. Backend-side ingest
  (`backend/core/ingest/rtmp_ingest.py`) is proven to work against a real
  RTMP push in dev, but isn't deployed to a real always-on host yet, and
  isn't wired into the trigger pipeline yet — see that module's docstring
  for the concrete next step.
- **RTSP URL** — direct URL entry, works if the phone/backend can reach
  the camera directly (same network, or port-forwarded).
- **Dahua P2P (experimental)** — same login as the DMSS app (serial +
  username + password). The backend fields exist and are stored
  (encrypted), but the actual P2P client
  (`backend/core/p2p/dahua_client.py`) is unfinished and has never been
  tested against a real Dahua device — see that module's docstring for
  exactly what's missing.
