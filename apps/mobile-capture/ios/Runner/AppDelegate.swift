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

  private let wearables: WearablesInterface = Wearables.shared
  private var streamSession: StreamSession?

  private var stateListenerToken: AnyListenerToken?
  private var videoFrameListenerToken: AnyListenerToken?
  private var errorListenerToken: AnyListenerToken?
  private var photoDataListenerToken: AnyListenerToken?

  private var configured = false

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
        let permission = Permission.camera
        var status = try await wearables.checkPermissionStatus(permission)
        if status != .granted {
          status = try await wearables.requestPermission(permission)
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
      videoCodec: VideoCodec.raw,
      resolution: resolution,
      frameRate: safeFps
    )

    let selector = AutoDeviceSelector(wearables: wearables)
    let session = StreamSession(streamSessionConfig: sessionConfig, deviceSelector: selector)

    stateListenerToken = session.statePublisher.listen { _ in }

    videoFrameListenerToken = session.videoFramePublisher.listen { [weak self] frame in
      guard let image = frame.makeUIImage() else {
        return
      }
      guard let data = image.jpegData(compressionQuality: 0.72) else {
        return
      }
      self?.onPreviewFrame?(data)
    }

    photoDataListenerToken = session.photoDataPublisher.listen { [weak self] photoData in
      self?.onCapturedPhoto?(photoData.data)
    }

    errorListenerToken = session.errorPublisher.listen { error in
      NSLog("[Aesthetica][DAT] Stream error: \(error)")
    }

    streamSession = session

    Task {
      await session.start()
      completion(.success(()))
    }
  }

  func stopStream(completion: @escaping (Result<Void, Error>) -> Void) {
    guard let session = streamSession else {
      completion(.success(()))
      return
    }

    Task {
      await session.stop()
      streamSession = nil
      stateListenerToken = nil
      videoFrameListenerToken = nil
      photoDataListenerToken = nil
      errorListenerToken = nil
      completion(.success(()))
    }
  }

  func capturePhoto(completion: @escaping (Result<Void, Error>) -> Void) {
    guard let session = streamSession else {
      completion(.failure(DatBridgeError.notInitialized))
      return
    }
    session.capturePhoto(format: .jpeg)
    completion(.success(()))
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
