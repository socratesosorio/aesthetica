import AVFoundation
import Flutter
import UIKit

#if canImport(MWDATCore)
import MWDATCore
#endif

#if canImport(MWDATCamera)
import MWDATCamera
#endif

@main
@objc class AppDelegate: FlutterAppDelegate {
  private var datBridge: DatFlutterBridge?

  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    GeneratedPluginRegistrant.register(with: self)
    let started = super.application(application, didFinishLaunchingWithOptions: launchOptions)

    guard let controller = window?.rootViewController as? FlutterViewController else {
      return started
    }

    datBridge = DatFlutterBridge(messenger: controller.binaryMessenger)
    return started
  }

  override func application(
    _ app: UIApplication,
    open url: URL,
    options: [UIApplication.OpenURLOptionsKey: Any] = [:]
  ) -> Bool {
    if datBridge?.handleOpenURL(url) == true {
      return true
    }
    return super.application(app, open: url, options: options)
  }
}

private struct StreamConfig {
  let width: Int
  let height: Int
  let fps: Int
}

private enum DatBridgeError: Error {
  case invalidArgs
  case unavailable(String)
  case permissionDenied
  case notInitialized
  case streamStartFailed
  case noFrameAvailable

  var code: String {
    switch self {
    case .invalidArgs:
      return "invalid_args"
    case .unavailable:
      return "unavailable"
    case .permissionDenied:
      return "permission_denied"
    case .notInitialized:
      return "not_initialized"
    case .streamStartFailed:
      return "stream_start_failed"
    case .noFrameAvailable:
      return "no_frame_available"
    }
  }

  var message: String {
    switch self {
    case .invalidArgs:
      return "Invalid method arguments"
    case let .unavailable(msg):
      return msg
    case .permissionDenied:
      return "Camera permission denied"
    case .notInitialized:
      return "SDK/provider not initialized"
    case .streamStartFailed:
      return "Failed to start stream"
    case .noFrameAvailable:
      return "No frame available for fallback photo capture"
    }
  }
}

private final class EventSinkHandler: NSObject, FlutterStreamHandler {
  var sink: FlutterEventSink?

  func onListen(withArguments arguments: Any?, eventSink events: @escaping FlutterEventSink) -> FlutterError? {
    sink = events
    return nil
  }

  func onCancel(withArguments arguments: Any?) -> FlutterError? {
    sink = nil
    return nil
  }
}

private protocol DatFrameProvider: AnyObject {
  var onPreviewFrame: ((Data) -> Void)? { get set }
  var onCapturedPhoto: ((Data) -> Void)? { get set }

  func initialize(completion: @escaping (Result<Void, Error>) -> Void)
  func requestCameraPermission(completion: @escaping (Result<Void, Error>) -> Void)
  func startStream(config: StreamConfig, completion: @escaping (Result<Void, Error>) -> Void)
  func stopStream(completion: @escaping (Result<Void, Error>) -> Void)
  func capturePhoto(completion: @escaping (Result<Void, Error>) -> Void)
  func handleOpenURL(_ url: URL) -> Bool
}

private final class DatFlutterBridge {
  private let methodChannel: FlutterMethodChannel
  private let frameEventChannel: FlutterEventChannel
  private let photoEventChannel: FlutterEventChannel

  private let frameSinkHandler = EventSinkHandler()
  private let photoSinkHandler = EventSinkHandler()

  private var provider: DatFrameProvider
  private var initialized = false

  init(messenger: FlutterBinaryMessenger) {
    methodChannel = FlutterMethodChannel(name: "aesthetica/dat", binaryMessenger: messenger)
    frameEventChannel = FlutterEventChannel(name: "aesthetica/dat_frames", binaryMessenger: messenger)
    photoEventChannel = FlutterEventChannel(name: "aesthetica/dat_photo_captures", binaryMessenger: messenger)

    provider = DatProviderFactory.makeProvider()

    provider.onPreviewFrame = { [weak self] data in
      guard let sink = self?.frameSinkHandler.sink else {
        return
      }
      sink(FlutterStandardTypedData(bytes: data))
    }

    provider.onCapturedPhoto = { [weak self] data in
      guard let sink = self?.photoSinkHandler.sink else {
        return
      }
      sink(FlutterStandardTypedData(bytes: data))
    }

    frameEventChannel.setStreamHandler(frameSinkHandler)
    photoEventChannel.setStreamHandler(photoSinkHandler)

    methodChannel.setMethodCallHandler { [weak self] call, result in
      self?.handleMethod(call, result: result)
    }
  }

  func handleOpenURL(_ url: URL) -> Bool {
    provider.handleOpenURL(url)
  }

  private func handleMethod(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
    switch call.method {
    case "initializeSdk":
      provider.initialize { [weak self] completion in
        if case .success = completion {
          self?.initialized = true
        }
        Self.finish(result: result, completion)
      }

    case "requestCameraPermission":
      provider.requestCameraPermission { completion in
        Self.finish(result: result, completion)
      }

    case "startVideoStream":
      guard initialized else {
        result(Self.flutterError(from: DatBridgeError.notInitialized))
        return
      }
      guard
        let args = call.arguments as? [String: Any],
        let width = args["width"] as? Int,
        let height = args["height"] as? Int,
        let fps = args["fps"] as? Int
      else {
        result(Self.flutterError(from: DatBridgeError.invalidArgs))
        return
      }

      let config = StreamConfig(width: width, height: height, fps: fps)
      provider.startStream(config: config) { completion in
        Self.finish(result: result, completion)
      }

    case "stopVideoStream":
      provider.stopStream { completion in
        Self.finish(result: result, completion)
      }

    case "capturePhoto":
      provider.capturePhoto { completion in
        Self.finish(result: result, completion)
      }

    default:
      result(FlutterMethodNotImplemented)
    }
  }

  private static func finish(result: @escaping FlutterResult, _ completion: Result<Void, Error>) {
    DispatchQueue.main.async {
      switch completion {
      case .success:
        result(nil)
      case let .failure(error):
        result(flutterError(from: error))
      }
    }
  }

  private static func flutterError(from error: Error) -> FlutterError {
    if let e = error as? DatBridgeError {
      return FlutterError(code: e.code, message: e.message, details: nil)
    }
    return FlutterError(code: "native_error", message: error.localizedDescription, details: nil)
  }
}

private enum DatProviderFactory {
  static func makeProvider() -> DatFrameProvider {
    let forceFallback = (Bundle.main.object(forInfoDictionaryKey: "AESTHETICA_FORCE_PHONE_CAMERA_FALLBACK") as? Bool) ?? false

    if !forceFallback {
      #if canImport(MWDATCore) && canImport(MWDATCamera)
      return MetaDatProvider()
      #endif
    }

    return AVCaptureFallbackProvider()
  }
}

private final class AVCaptureFallbackProvider: NSObject, DatFrameProvider {
  var onPreviewFrame: ((Data) -> Void)?
  var onCapturedPhoto: ((Data) -> Void)?

  private let session = AVCaptureSession()
  private let output = AVCaptureVideoDataOutput()
  private let queue = DispatchQueue(label: "aesthetica.camera.frames")
  private let ciContext = CIContext(options: nil)
  private var isConfigured = false
  private var latestFrameData: Data?

  func initialize(completion: @escaping (Result<Void, Error>) -> Void) {
    completion(.success(()))
  }

  func requestCameraPermission(completion: @escaping (Result<Void, Error>) -> Void) {
    AVCaptureDevice.requestAccess(for: .video) { granted in
      DispatchQueue.main.async {
        if granted {
          completion(.success(()))
        } else {
          completion(.failure(DatBridgeError.permissionDenied))
        }
      }
    }
  }

  func startStream(config: StreamConfig, completion: @escaping (Result<Void, Error>) -> Void) {
    queue.async { [weak self] in
      guard let self else {
        completion(.failure(DatBridgeError.streamStartFailed))
        return
      }

      do {
        try self.configureSessionIfNeeded(config: config)
        if !self.session.isRunning {
          self.session.startRunning()
        }
        completion(.success(()))
      } catch {
        completion(.failure(error))
      }
    }
  }

  func stopStream(completion: @escaping (Result<Void, Error>) -> Void) {
    queue.async { [weak self] in
      guard let self else {
        completion(.success(()))
        return
      }

      if self.session.isRunning {
        self.session.stopRunning()
      }
      completion(.success(()))
    }
  }

  func capturePhoto(completion: @escaping (Result<Void, Error>) -> Void) {
    queue.async { [weak self] in
      guard let self else {
        completion(.failure(DatBridgeError.noFrameAvailable))
        return
      }
      guard let frame = self.latestFrameData else {
        completion(.failure(DatBridgeError.noFrameAvailable))
        return
      }

      self.onCapturedPhoto?(frame)
      completion(.success(()))
    }
  }

  func handleOpenURL(_ url: URL) -> Bool {
    false
  }

  private func configureSessionIfNeeded(config: StreamConfig) throws {
    if isConfigured {
      return
    }

    session.beginConfiguration()
    defer {
      session.commitConfiguration()
    }

    let desired = max(config.width, config.height)
    if desired >= 1280 {
      session.sessionPreset = .hd1280x720
    } else if desired >= 960 {
      session.sessionPreset = .iFrame960x540
    } else {
      session.sessionPreset = .vga640x480
    }

    guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
      throw DatBridgeError.unavailable("No camera device available")
    }

    let input = try AVCaptureDeviceInput(device: device)
    guard session.canAddInput(input) else {
      throw DatBridgeError.unavailable("Cannot add camera input")
    }
    session.addInput(input)

    output.videoSettings = [
      kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32BGRA),
    ]
    output.alwaysDiscardsLateVideoFrames = true
    output.setSampleBufferDelegate(self, queue: queue)

    guard session.canAddOutput(output) else {
      throw DatBridgeError.unavailable("Cannot add video output")
    }
    session.addOutput(output)

    isConfigured = true
  }
}

extension AVCaptureFallbackProvider: AVCaptureVideoDataOutputSampleBufferDelegate {
  func captureOutput(
    _ output: AVCaptureOutput,
    didOutput sampleBuffer: CMSampleBuffer,
    from connection: AVCaptureConnection
  ) {
    guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else {
      return
    }

    let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
    guard let cgImage = ciContext.createCGImage(ciImage, from: ciImage.extent) else {
      return
    }

    let uiImage = UIImage(cgImage: cgImage)
    guard let jpeg = uiImage.jpegData(compressionQuality: 0.72) else {
      return
    }

    latestFrameData = jpeg
    onPreviewFrame?(jpeg)
  }
}

#if canImport(MWDATCore) && canImport(MWDATCamera)
private final class MetaDatProvider: DatFrameProvider {
  var onPreviewFrame: ((Data) -> Void)?
  var onCapturedPhoto: ((Data) -> Void)?

  private lazy var wearables: WearablesInterface = Wearables.shared
  private var streamSession: StreamSession?
  private var deviceSelector: AutoDeviceSelector?
  private var deviceMonitorTask: Task<Void, Never>?

  private var stateListenerToken: AnyListenerToken?
  private var videoFrameListenerToken: AnyListenerToken?
  private var errorListenerToken: AnyListenerToken?
  private var photoDataListenerToken: AnyListenerToken?

  private var configured = false
  private var currentStreamState: String = "none"
  private var frameCount: Int = 0

  func initialize(completion: @escaping (Result<Void, Error>) -> Void) {
    do {
      if !configured {
        try Wearables.configure()
        configured = true
      }
      completion(.success(()))
    } catch {
      completion(.failure(error))
    }
  }

  func requestCameraPermission(completion: @escaping (Result<Void, Error>) -> Void) {
    Task {
      do {
        // Step 1: Register with the Meta AI app if not already registered.
        let regState = wearables.registrationState
        NSLog("[Aesthetica][DAT] Current registration state: \(regState)")

        if regState != .registered {
          NSLog("[Aesthetica][DAT] Starting registration flow (will open Meta AI app)...")
          try await wearables.startRegistration()
          NSLog("[Aesthetica][DAT] startRegistration() returned, waiting for state...")

          // Wait for the registration state to settle after the
          // Meta AI app redirects back.
          for await state in wearables.registrationStateStream() {
            NSLog("[Aesthetica][DAT] Registration state update: \(state)")
            if state == .registered { break }
            if state == .unavailable {
              throw DatBridgeError.unavailable("Registration failed — glasses not available")
            }
          }
        }

        NSLog("[Aesthetica][DAT] Registered. Waiting for glasses to connect...")

        // Step 2: Wait for a device (glasses) to become available.
        // The official Meta sample waits for activeDeviceStream() before
        // requesting permission. Without a connected device the permission
        // request fails with PermissionError 0.
        let selector = AutoDeviceSelector(wearables: wearables)
        var deviceFound = false
        let timeout: UInt64 = 30_000_000_000 // 30 seconds in nanoseconds

        // Race between device appearing and a timeout
        try await withThrowingTaskGroup(of: Bool.self) { group in
          group.addTask {
            for await device in selector.activeDeviceStream() {
              if device != nil {
                NSLog("[Aesthetica][DAT] Device found: \(String(describing: device))")
                return true
              }
            }
            return false
          }
          group.addTask {
            try await Task.sleep(nanoseconds: timeout)
            return false
          }

          if let result = try await group.next() {
            deviceFound = result
          }
          group.cancelAll()
        }

        if !deviceFound {
          // Also check the current devices list in case it was already there.
          if wearables.devices.isEmpty {
            NSLog("[Aesthetica][DAT] No device found after 30s timeout.")
            throw DatBridgeError.unavailable(
              "No glasses found. Make sure your Ray-Bans are on, charged, and connected in the Meta AI app."
            )
          }
          NSLog("[Aesthetica][DAT] Device already in devices list, continuing.")
        }

        NSLog("[Aesthetica][DAT] Device available. Requesting camera permission...")

        // Step 3: Request camera permission (now that a device is connected).
        let permission = Permission.camera
        var status = try await wearables.checkPermissionStatus(permission)
        NSLog("[Aesthetica][DAT] Camera permission status: \(status)")

        if status != .granted {
          status = try await wearables.requestPermission(permission)
          NSLog("[Aesthetica][DAT] Camera permission after request: \(status)")
        }

        if status == .granted {
          completion(.success(()))
        } else {
          completion(.failure(DatBridgeError.permissionDenied))
        }
      } catch {
        NSLog("[Aesthetica][DAT] Permission flow error: \(error)")
        completion(.failure(error))
      }
    }
  }

  func startStream(config: StreamConfig, completion: @escaping (Result<Void, Error>) -> Void) {
    let resolution: StreamingResolution
    let longest = max(config.width, config.height)
    if longest >= 1280 {
      resolution = .high
    } else if longest >= 896 {
      resolution = .medium
    } else {
      resolution = .low
    }

    let safeFps = UInt(max(15, min(config.fps, 30)))
    let sessionConfig = StreamSessionConfig(
      videoCodec: VideoCodec.raw,
      resolution: resolution,
      frameRate: safeFps
    )

    NSLog("[Aesthetica][DAT] Creating stream session: resolution=\(resolution), fps=\(safeFps)")

    Task { @MainActor in
      // Retain the selector as an instance property (matches official sample).
      let selector = AutoDeviceSelector(wearables: wearables)
      self.deviceSelector = selector

      let session = StreamSession(streamSessionConfig: sessionConfig, deviceSelector: selector)

      // Monitor device availability (matches official sample pattern).
      self.deviceMonitorTask?.cancel()
      self.deviceMonitorTask = Task { @MainActor in
        for await device in selector.activeDeviceStream() {
          NSLog("[Aesthetica][DAT] Active device changed: \(device != nil ? "connected" : "none")")
        }
      }

      // State listener — dispatch back to MainActor (matches official sample).
      stateListenerToken = session.statePublisher.listen { [weak self] state in
        Task { @MainActor [weak self] in
          self?.currentStreamState = "\(state)"
          NSLog("[Aesthetica][DAT] Stream session state → \(state)")
        }
      }

      // Video frame listener.
      videoFrameListenerToken = session.videoFramePublisher.listen { [weak self] frame in
        Task { @MainActor [weak self] in
          guard let self else { return }
          self.frameCount += 1
          if self.frameCount == 1 {
            NSLog("[Aesthetica][DAT] First video frame received!")
          }
          if self.frameCount % 100 == 0 {
            NSLog("[Aesthetica][DAT] Received \(self.frameCount) frames, state=\(self.currentStreamState)")
          }
          guard let image = frame.makeUIImage() else { return }
          guard let data = image.jpegData(compressionQuality: 0.72) else { return }
          self.onPreviewFrame?(data)
        }
      }

      // Error listener.
      errorListenerToken = session.errorPublisher.listen { error in
        Task { @MainActor in
          NSLog("[Aesthetica][DAT] Stream error: \(error)")
        }
      }

      // Photo capture listener (fires for BOTH hardware button and programmatic capturePhoto).
      // This MUST be set up and the token retained for the lifetime of the session.
      photoDataListenerToken = session.photoDataPublisher.listen { [weak self] photoData in
        Task { @MainActor [weak self] in
          guard let self else { return }
          NSLog("[Aesthetica][DAT] ★ PHOTO RECEIVED ★ size=\(photoData.data.count) bytes, streamState=\(self.currentStreamState)")
          self.onCapturedPhoto?(photoData.data)
        }
      }

      NSLog("[Aesthetica][DAT] All listeners attached. photoDataListenerToken is \(photoDataListenerToken == nil ? "nil ⚠️" : "set ✓")")

      streamSession = session

      // Log initial state before starting.
      NSLog("[Aesthetica][DAT] Session initial state: \(session.state)")
      NSLog("[Aesthetica][DAT] Current devices: \(wearables.devices)")
      NSLog("[Aesthetica][DAT] Starting stream session...")

      await session.start()

      NSLog("[Aesthetica][DAT] Stream session started. state=\(session.state)")
      completion(.success(()))
    }
  }

  func stopStream(completion: @escaping (Result<Void, Error>) -> Void) {
    guard let session = streamSession else {
      completion(.success(()))
      return
    }

    Task { @MainActor in
      await session.stop()
      deviceMonitorTask?.cancel()
      deviceMonitorTask = nil
      streamSession = nil
      deviceSelector = nil
      stateListenerToken = nil
      videoFrameListenerToken = nil
      photoDataListenerToken = nil
      errorListenerToken = nil
      frameCount = 0
      currentStreamState = "stopped"
      NSLog("[Aesthetica][DAT] Stream session stopped and cleaned up.")
      completion(.success(()))
    }
  }

  func capturePhoto(completion: @escaping (Result<Void, Error>) -> Void) {
    NSLog("[Aesthetica][DAT] capturePhoto() called. streamSession=\(streamSession == nil ? "nil ⚠️" : "exists"), state=\(currentStreamState), frames=\(frameCount)")
    guard let session = streamSession else {
      NSLog("[Aesthetica][DAT] capturePhoto() FAILED: no active session")
      completion(.failure(DatBridgeError.notInitialized))
      return
    }
    Task { @MainActor in
      NSLog("[Aesthetica][DAT] Calling session.capturePhoto(format: .jpeg)...")
      session.capturePhoto(format: .jpeg)
      NSLog("[Aesthetica][DAT] session.capturePhoto() returned")
      completion(.success(()))
    }
  }

  func handleOpenURL(_ url: URL) -> Bool {
    guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
      return false
    }

    let isDatCallback = components.queryItems?.contains(where: { $0.name == "metaWearablesAction" }) == true
    guard isDatCallback else {
      return false
    }

    Task {
      do {
        _ = try await wearables.handleUrl(url)
      } catch {
        NSLog("[Aesthetica][DAT] handleUrl failed: \(error)")
      }
    }

    return true
  }
}
#endif
