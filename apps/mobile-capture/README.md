# mobile-capture

Flutter companion app for Meta Ray-Ban DAT stream capture.

## DAT Integration Notes

- `DatService` is the abstraction for DAT SDK calls.
- `RealDatService` uses `MethodChannel('aesthetica/dat')` and `EventChannel('aesthetica/dat_frames')`.
- Hook your native DAT SDK integration to these channel methods:
  - `initializeSdk`
  - `requestCameraPermission`
  - `startVideoStream` (`width`, `height`, `fps`)
  - `stopVideoStream`
- Current fallback for local dev is `MockDatService`.

## Run

```bash
flutter pub get
flutter run --dart-define=USE_MOCK_DAT=true --dart-define=API_BASE_URL=http://10.0.2.2:8000 --dart-define=API_TOKEN=dev
```

For a physical device, replace API host with your machine's LAN IP.
