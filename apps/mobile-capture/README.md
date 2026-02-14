# mobile-capture

Flutter companion app for Meta Ray-Ban DAT stream capture.

## DAT Integration Notes

- `DatService` is the abstraction for DAT SDK calls.
- `RealDatService` uses `MethodChannel('aesthetica/dat')` and `EventChannel('aesthetica/dat_frames')`.
- iOS bridge is implemented in `ios/Runner/AppDelegate.swift`:
  - method channel: `aesthetica/dat`
  - event channel: `aesthetica/dat_frames`
  - methods: `initializeSdk`, `requestCameraPermission`, `startVideoStream`, `stopVideoStream`
- Provider routing:
  - DAT provider is used when `MWDATCore` + `MWDATCamera` are available.
  - AVFoundation fallback stream is used otherwise.

## iOS DAT Setup

1. Add Meta DAT package in Xcode (`Runner` target):
   - SPM URL: `https://github.com/facebook/meta-wearables-dat-ios`
2. Configure `ios/Runner/Info.plist`:
   - set `MWDAT.MetaAppID`
   - keep `MWDAT.AppLinkURLScheme` aligned with your Meta app setup
3. Keep `AESTHETICA_FORCE_PHONE_CAMERA_FALLBACK=false`.
4. Pair glasses via Meta AI app before launching capture.

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
