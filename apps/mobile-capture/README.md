# mobile-capture

Flutter companion app for Meta Ray-Ban DAT stream capture.

## DAT Integration Notes

- `DatService` is the abstraction for DAT SDK calls.
- `RealDatService` uses `MethodChannel('aesthetica/dat')` and `EventChannel('aesthetica/dat_frames')`.
- `RealDatService` also subscribes to `EventChannel('aesthetica/dat_photo_captures')`.
- iOS bridge is implemented in `ios/Runner/AppDelegate.swift`:
  - method channel: `aesthetica/dat`
  - event channel: `aesthetica/dat_frames`
  - photo event channel: `aesthetica/dat_photo_captures`
  - methods: `initializeSdk`, `requestCameraPermission`, `startVideoStream`, `stopVideoStream`, `capturePhoto`
- Provider routing:
  - DAT provider is used when `MWDATCore` + `MWDATCamera` are available.
  - AVFoundation fallback stream is used otherwise.

## iOS DAT Setup

1. Add Meta DAT package in Xcode (`Runner` target):
   - SPM URL: `https://github.com/facebook/meta-wearables-dat-ios`
2. Configure `ios/Runner/Info.plist`:
   - set `MWDAT.MetaAppID`
   - set `MWDAT.ClientToken`
   - keep `MWDAT.AppLinkURLScheme` aligned with your Meta app setup
3. Keep `AESTHETICA_FORCE_PHONE_CAMERA_FALLBACK=false`.
4. Pair glasses via Meta AI app before launching capture.
5. Ensure your app has:
   - `UIBackgroundModes`: `bluetooth-peripheral`, `external-accessory`
   - `UISupportedExternalAccessoryProtocols`: `com.meta.ar.wearable`

## Hardware-Button Capture Flow

- Start the app once and connect/pair via DAT.
- The glasses hardware camera button triggers DAT photo events.
- App auto-receives photo bytes, runs preprocessing, and uploads to backend automatically.
- The in-app button now triggers remote `capturePhoto` on DAT, but is optional.

## Display Glasses Note

- DAT `0.4.0` adds support for Meta Ray-Ban Display hardware compatibility.
- Public iOS DAT APIs currently expose camera/stream/photo flows (no public custom on-glasses UI rendering API in the sample/reference surface yet).
- This app is ready to add that module when Meta exposes it publicly.

## Run

```bash
flutter pub get
flutter run --dart-define=USE_MOCK_DAT=false --dart-define=API_BASE_URL=http://127.0.0.1:8000 --dart-define=API_TOKEN=dev
```

For a physical iPhone, replace API host with your machine's LAN IP.

## Fallback Mode

To force phone-camera fallback on iOS (no glasses), set:
- `AESTHETICA_FORCE_PHONE_CAMERA_FALLBACK=true` in `Info.plist`
or run:
- `flutter run --dart-define=USE_MOCK_DAT=true`
