# VisionOS Android — Setup

## Firebase project — real, one manual step left

`android/app/google-services.json` now points at a **real** Firebase
project (`visionos-platform`, GCP project number `504980287958`), created
and wired up via the Firebase Management API. Firebase Auth is initialized
for it. The one piece that could **not** be done via API: Google enabling
Google Sign-In as a provider requires an OAuth 2.0 client, and creating
those programmatically requires the IAP OAuth Admin API — which Google
discontinued for new/personal (non-Workspace-org) projects. This is a
platform limitation, not something scriptable around.

**To finish it (2 minutes):**
1. [Firebase Console](https://console.firebase.google.com/project/visionos-platform/authentication/providers)
   → Authentication → Sign-in method → enable **Google**.
2. That auto-creates the OAuth Web client. Re-download
   `google-services.json` from Project Settings → General → Your apps, and
   replace `android/app/google-services.json` with it.
3. Copy the new file's `oauth_client[0].client_id` value into
   `android/app/src/main/res/values/strings.xml`'s
   `google_sign_in_web_client_id` string (currently empty on purpose —
   see the comment above it for why it's not just the
   plugin-auto-generated `default_web_client_id` resource).
4. Rebuild. Until step 1 is done, the app builds and runs fine — the
   "Sign in with Google" button is just disabled with an explanatory
   message (`LoginScreen.kt`).

### Backend URL (`ApiClient.kt`)

Points at `https://visionos-1004956364101.asia-south1.run.app/`, already
in the codebase — verify this is actually your deployed backend before
relying on it. Note: `infrastructure/deploy.sh` deploys to a *different*
GCP project (`rux-view-497104`) than the Firebase project above
(`visionos-platform`) — these were provisioned separately; worth
reconciling into one project when you have a moment, not urgent.

## Building

```bash
cd android
gradle assembleDebug   # no wrapper committed yet -- see below
# Output: android/app/build/outputs/apk/debug/app-debug.apk
```

This APK is **debug-signed** (Android's auto-generated debug keystore) —
installable by sideloading (enable "Install unknown apps" for whatever
you use to transfer the file), but not Play Store-ready. For a Play
Store release you'll need your own upload keystore and a
`buildTypes { release { signingConfig = ... } }` block, plus a Play
Console account. No Gradle wrapper (`gradlew`) is committed yet — add one
with `gradle wrapper` if you want a pinned Gradle version instead of
relying on a system install.

## What "Add Camera" actually does right now

Three connection types (see `AddCameraScreen.kt`):

- **RTMP Push (recommended)** — generates a unique `rtmp://.../live/<key>`
  URL server-side, shown after creation. You enter that in your DVR's
  "Platform Access" / "RTMP" / "Push Stream" menu.
  `backend/core/ingest/rtmp_ingest.py` (frame sampling) and
  `rtmp_poller.py` (the 20s APScheduler job feeding sampled frames
  through the same session-merge pipeline an HTTP trigger uses) are both
  built and tested. **Not yet real**: MediaMTX (the media server that
  actually receives the RTMP push) isn't deployed anywhere with a public
  IP — `visionos-platform` has no billing account linked, and Compute
  Engine requires one. That's the one remaining blocker to this being a
  genuinely working end-to-end path; needs a billing account attached
  (your call, real money, not something to do without asking).
- **RTSP URL** — direct URL entry, works if the phone/backend can reach
  the camera directly (same network, or port-forwarded).
- **Dahua P2P (experimental)** — same login as the DMSS app (serial +
  username + password). Backend fields exist and are stored (encrypted),
  but the actual P2P client (`backend/core/p2p/dahua_client.py`) is
  unfinished and has never been tested against a real Dahua device.
