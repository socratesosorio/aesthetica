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
    }
  }
}

private protocol DatFrameProvider: AnyObject {
  var onFrame: ((Data) -> Void)? { get set }

  func initialize(completion: @escaping (Result<Void, Error>) -> Void)
  func requestCameraPermission(completion: @escaping (Result<Void, Error>) -> Void)
  func startStream(config: StreamConfig, completion: @escaping (Result<Void, Error>) -> Void)
  func stopStream(completion: @escaping (Result<Void, Error>) -> Void)
  func handleOpenURL(_ url: URL) -> Bool
}

private final class DatFlutterBridge: NSObject, FlutterStreamHandler {
  private let methodChannel: FlutterMethodChannel
  private let eventChannel: FlutterEventChannel

  private var eventSink: FlutterEventSink?
  private var provider: DatFrameProvider
  private var initialized = false

  init(messenger: FlutterBinaryMessenger) {
    methodChannel = FlutterMethodChannel(name: "aesthetica/dat", binaryMessenger: messenger)
    eventChannel = FlutterEventChannel(name: "aesthetica/dat_frames", binaryMessenger: messenger)

    provider = DatProviderFactory.makeProvider()
    super.init()

    provider.onFrame = { [weak self] data in
      guard let sink = self?.eventSink else {
        return
      }
      sink(FlutterStandardTypedData(bytes: data))
    }

    eventChannel.setStreamHandler(self)
    methodChannel.setMethodCallHandler(handleMethod)
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

    default:
      result(FlutterMethodNotImplemented)
    }
  }

  static func flutterError(from error: Error) -> FlutterError {
    if let e = error as? DatBridgeError {
      return FlutterError(code: e.code, message: e.message, details: nil)
    }
    return FlutterError(code: "native_error", message: error.localizedDescription, details: nil)
  }

  static func finish(result: @escaping FlutterResult, _ completion: Result<Void, Error>) {
    DispatchQueue.main.async {
      switch completion {
      case .success:
        result(nil)
      case let .failure(error):
        result(flutterError(from: error))
      }
    }
  }

  func onListen(withArguments arguments: Any?, eventSink events: @escaping FlutterEventSink) -> FlutterError? {
    eventSink = events
    return nil
  }

  func onCancel(withArguments arguments: Any?) -> FlutterError? {
    eventSink = nil
    return nil
  }
}

private enum DatProviderFactory {
  static func makeProvider() -> DatFrameProvider {
    // Set to true in Info.plist only when DAT SDK + app registration is configured.
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
  var onFrame: ((Data) -> Void)?

  private let session = AVCaptureSession()
  private let output = AVCaptureVideoDataOutput()
  private let queue = DispatchQueue(label: "aesthetica.camera.frames")
  private let ciContext = CIContext(options: nil)
  private var isConfigured = false

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

    onFrame?(jpeg)
  }
}

#if canImport(MWDATCore) && canImport(MWDATCamera)
private final class MetaDatProvider: DatFrameProvider {
  var onFrame: ((Data) -> Void)?

  private var streamSession: StreamSession?
  private var stateListenerToken: Any?
  private var frameListenerToken: Any?
  private var errorListenerToken: Any?

  private var configured = false
  private let wearables = Wearables.shared

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
        var status = try await wearables.checkPermissionStatus(.camera)
        if status != .granted {
          status = try await wearables.requestPermission(.camera)
        }
        if status == .granted {
          completion(.success(()))
        } else {
          completion(.failure(DatBridgeError.permissionDenied))
        }
      } catch {
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
      videoCodec: .raw,
      resolution: resolution,
      frameRate: safeFps
    )

    let selector = AutoDeviceSelector(wearables: wearables)
    let session = StreamSession(streamSessionConfig: sessionConfig, deviceSelector: selector)

    // Keep refs to listener tokens to maintain subscriptions.
    stateListenerToken = session.statePublisher.listen { _ in }
    frameListenerToken = session.videoFramePublisher.listen { [weak self] frame in
      guard let image = frame.makeUIImage() else {
        return
      }
      guard let data = image.jpegData(compressionQuality: 0.72) else {
        return
      }
      self?.onFrame?(data)
    }

    errorListenerToken = session.errorPublisher.listen { error in
      NSLog("[Aesthetica][DAT] Stream error: \(error)")
    }

    streamSession = session
    session.start()
    completion(.success(()))
  }

  func stopStream(completion: @escaping (Result<Void, Error>) -> Void) {
    streamSession?.stop()
    streamSession = nil
    stateListenerToken = nil
    frameListenerToken = nil
    errorListenerToken = nil
    completion(.success(()))
  }

  func handleOpenURL(_ url: URL) -> Bool {
    guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
      return false
    }

    let hasMetaAction = components.queryItems?.contains(where: { $0.name == "metaWearablesAction" }) == true
    guard hasMetaAction else {
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
