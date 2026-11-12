import CryptoKit
import UIKit

private enum ProbeTrace {
  static func record(_ event: String, _ fields: [String: Any] = [:]) {
    var value = fields
    value["event"] = event
    value["time"] = Date().timeIntervalSince1970
    do {
      let directory = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
      try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
      let url = directory.appendingPathComponent("open-with-events.jsonl")
      if !FileManager.default.fileExists(atPath: url.path) {
        FileManager.default.createFile(atPath: url.path, contents: nil)
      }
      let file = try FileHandle(forWritingTo: url)
      defer { try? file.close() }
      try file.seekToEnd()
      try file.write(contentsOf: JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]) + Data([10]))
    } catch {
      NSLog("Probe trace error: %@", String(describing: error))
    }
  }
}

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
  func application(_ application: UIApplication,
                   configurationForConnecting session: UISceneSession,
                   options: UIScene.ConnectionOptions) -> UISceneConfiguration {
    ProbeTrace.record("configuration", ["urls": options.urlContexts.count,
                                         "activities": options.userActivities.map(\.activityType)])
    let configuration = UISceneConfiguration(name: "Default", sessionRole: session.role)
    configuration.delegateClass = SceneDelegate.self
    return configuration
  }
}

final class SceneDelegate: UIResponder, UIWindowSceneDelegate {
  var window: UIWindow?
  private let receipt = UILabel()
  private let fixtureStatus = UILabel()
  private var isFixtureHost: Bool { Bundle.main.object(forInfoDictionaryKey: "ProbeRole") as? String == "fixture" }
  private var fixtureURL: URL {
    FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
      .appendingPathComponent("OpenWithProbe.gpx")
  }

  func scene(_ scene: UIScene, willConnectTo session: UISceneSession,
             options connectionOptions: UIScene.ConnectionOptions) {
    ProbeTrace.record("willConnect", ["urls": connectionOptions.urlContexts.count,
                                       "activities": connectionOptions.userActivities.map(\.activityType)])
    guard let scene = scene as? UIWindowScene else { return }
    let controller = UIViewController()
    controller.view.backgroundColor = .systemBackground
    let title = UILabel()
    title.text = Bundle.main.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String
    title.font = .preferredFont(forTextStyle: .title1)
    receipt.accessibilityIdentifier = "receipt"
    receipt.text = "WAITING"
    receipt.numberOfLines = 0
    fixtureStatus.accessibilityIdentifier = "fixtureStatus"
    fixtureStatus.numberOfLines = 0
    let stack = UIStackView(arrangedSubviews: [title, receipt, fixtureStatus])
    stack.axis = .vertical
    stack.spacing = 20
    stack.translatesAutoresizingMaskIntoConstraints = false
    controller.view.addSubview(stack)
    NSLayoutConstraint.activate([
      stack.leadingAnchor.constraint(equalTo: controller.view.safeAreaLayoutGuide.leadingAnchor, constant: 20),
      stack.trailingAnchor.constraint(equalTo: controller.view.safeAreaLayoutGuide.trailingAnchor, constant: -20),
      stack.centerYAnchor.constraint(equalTo: controller.view.centerYAnchor)
    ])
    let window = UIWindow(windowScene: scene)
    window.rootViewController = controller
    self.window = window
    window.makeKeyAndVisible()
    if isFixtureHost {
      do {
        // Never overwrite the source on reactivation: a later hash check must
        // detect any change made by a receiving application.
        if !UserDefaults.standard.bool(forKey: "ProbeFixtureSeeded") {
          try FileManager.default.copyItem(at: Bundle.main.url(forResource: "Fixture", withExtension: "gpx")!,
                                           to: fixtureURL)
          UserDefaults.standard.set(true, forKey: "ProbeFixtureSeeded")
        }
        refreshFixtureStatus()
      } catch {
        fixtureStatus.text = "ERROR: \(error)"
      }
    }
    handle(connectionOptions.urlContexts)
  }

  func sceneDidBecomeActive(_ scene: UIScene) {
    ProbeTrace.record("becameActive")
    if isFixtureHost { refreshFixtureStatus() }
  }

  func scene(_ scene: UIScene, openURLContexts contexts: Set<UIOpenURLContext>) {
    ProbeTrace.record("openURLContexts", ["urls": contexts.count])
    handle(contexts)
  }

  func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
    ProbeTrace.record("continueActivity", ["type": userActivity.activityType])
  }

  private func handle(_ contexts: Set<UIOpenURLContext>) {
    guard let context = contexts.first else { return }
    ProbeTrace.record("receivedURL", ["filename": context.url.lastPathComponent,
                                       "openInPlace": context.options.openInPlace])
    let scoped = context.url.startAccessingSecurityScopedResource()
    ProbeTrace.record("scope", ["granted": scoped])
    defer { if scoped { context.url.stopAccessingSecurityScopedResource() } }
    var result: [String: Any] = [
      "filename": context.url.lastPathComponent,
      "openInPlace": context.options.openInPlace,
      "securityScopeGranted": scoped,
      "readSucceeded": false
    ]
    var coordinationError: NSError?
    // The diagnostic receiver completes a coordinated read while its access
    // scope is alive. It does not claim CoMaps' asynchronous import is safe.
    ProbeTrace.record("coordinateBegin")
    NSFileCoordinator().coordinate(readingItemAt: context.url, options: [], error: &coordinationError) { url in
      ProbeTrace.record("coordinateAccessor")
      do {
        let data = try Data(contentsOf: url)
        result["readSucceeded"] = true
        result["bytes"] = data.count
        result["sha256"] = Self.digest(data)
      } catch {
        result["error"] = String(describing: error)
      }
    }
    ProbeTrace.record("coordinateEnd", ["error": coordinationError?.localizedDescription ?? ""])
    if let coordinationError { result["error"] = String(describing: coordinationError) }
    receipt.text = Self.json(result)
  }

  private func refreshFixtureStatus() {
    do {
      let data = try Data(contentsOf: fixtureURL)
      let attributes = try FileManager.default.attributesOfItem(atPath: fixtureURL.path)
      guard let modified = attributes[.modificationDate] as? Date else {
        fixtureStatus.text = "ERROR: missing modification date"
        return
      }
      fixtureStatus.text = Self.json(["sha256": Self.digest(data), "bytes": data.count,
                                     "modificationTime": modified.timeIntervalSince1970])
    } catch {
      fixtureStatus.text = "ERROR: \(error)"
    }
  }

  private static func digest(_ data: Data) -> String {
    SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
  }

  private static func json(_ value: [String: Any]) -> String {
    String(data: try! JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]), encoding: .utf8)!
  }
}
