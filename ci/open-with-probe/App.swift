import CryptoKit
import UIKit

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
  func application(_ application: UIApplication,
                   configurationForConnecting session: UISceneSession,
                   options: UIScene.ConnectionOptions) -> UISceneConfiguration {
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
        if !FileManager.default.fileExists(atPath: fixtureURL.path) {
          try FileManager.default.copyItem(at: Bundle.main.url(forResource: "Fixture", withExtension: "gpx")!,
                                           to: fixtureURL)
        }
        refreshFixtureStatus()
      } catch {
        fixtureStatus.text = "ERROR: \(error)"
      }
    }
    handle(connectionOptions.urlContexts)
  }

  func sceneDidBecomeActive(_ scene: UIScene) {
    if isFixtureHost { refreshFixtureStatus() }
  }

  func scene(_ scene: UIScene, openURLContexts contexts: Set<UIOpenURLContext>) {
    handle(contexts)
  }

  private func handle(_ contexts: Set<UIOpenURLContext>) {
    guard let context = contexts.first else { return }
    let scoped = context.url.startAccessingSecurityScopedResource()
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
    NSFileCoordinator().coordinate(readingItemAt: context.url, options: [], error: &coordinationError) { url in
      do {
        let data = try Data(contentsOf: url)
        result["readSucceeded"] = true
        result["bytes"] = data.count
        result["sha256"] = Self.digest(data)
      } catch {
        result["error"] = String(describing: error)
      }
    }
    if let coordinationError { result["error"] = String(describing: coordinationError) }
    receipt.text = Self.json(result)
  }

  private func refreshFixtureStatus() {
    do {
      let data = try Data(contentsOf: fixtureURL)
      fixtureStatus.text = Self.json(["sha256": Self.digest(data), "bytes": data.count])
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
