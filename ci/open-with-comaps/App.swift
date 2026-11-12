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
  private let status = UILabel()
  private let filenames = ["Cold.gpx", "Warm.gpx"]
  private let manager = FileManager.default
  private var documents: URL { manager.urls(for: .documentDirectory, in: .userDomainMask)[0] }
  private var marker: URL {
    manager.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
      .appendingPathComponent("CoMapsOpenWithFixtureSeed.json")
  }

  func scene(_ scene: UIScene, willConnectTo session: UISceneSession,
             options connectionOptions: UIScene.ConnectionOptions) {
    guard let scene = scene as? UIWindowScene else { return }
    let controller = UIViewController()
    controller.view.backgroundColor = .systemBackground
    status.accessibilityIdentifier = "fixtureStatus"
    status.numberOfLines = 0
    status.translatesAutoresizingMaskIntoConstraints = false
    controller.view.addSubview(status)
    NSLayoutConstraint.activate([
      status.leadingAnchor.constraint(equalTo: controller.view.safeAreaLayoutGuide.leadingAnchor, constant: 20),
      status.trailingAnchor.constraint(equalTo: controller.view.safeAreaLayoutGuide.trailingAnchor, constant: -20),
      status.centerYAnchor.constraint(equalTo: controller.view.centerYAnchor)
    ])
    let window = UIWindow(windowScene: scene)
    window.rootViewController = controller
    self.window = window
    window.makeKeyAndVisible()
    do {
      if !manager.fileExists(atPath: marker.path) {
        try manager.createDirectory(at: marker.deletingLastPathComponent(), withIntermediateDirectories: true)
        for filename in filenames {
          guard let source = Bundle.main.url(forResource: filename, withExtension: nil) else {
            throw CocoaError(.fileNoSuchFile)
          }
          let destination = documents.appendingPathComponent(filename)
          // copyItem fails if a partial previous seed exists. Never overwrite.
          try manager.copyItem(at: source, to: destination)
          try manager.setAttributes([.modificationDate: Date(timeIntervalSince1970: 1_700_000_000)],
                                    ofItemAtPath: destination.path)
        }
        // A durable marker outside Documents prevents recreation on every
        // later launch, including XCTest's own fixture-host launch.
        try JSONSerialization.data(withJSONObject: inventory(), options: [.sortedKeys]).write(to: marker, options: [.atomic])
      }
      refresh()
    } catch {
      status.text = "ERROR: \(error)"
    }
  }

  func sceneDidBecomeActive(_ scene: UIScene) { refresh() }

  private func inventory() throws -> [String: Any] {
    var result: [String: Any] = [:]
    for filename in filenames {
      let url = documents.appendingPathComponent(filename)
      let data = try Data(contentsOf: url)
      let attributes = try manager.attributesOfItem(atPath: url.path)
      guard let date = attributes[.modificationDate] as? Date else { throw CocoaError(.fileReadUnknown) }
      result[filename] = ["bytes": data.count,
                          "sha256": SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined(),
                          "modificationTime": date.timeIntervalSince1970]
    }
    return result
  }

  private func refresh() {
    do {
      status.text = String(decoding: try JSONSerialization.data(withJSONObject: inventory(), options: [.sortedKeys]), as: UTF8.self)
    } catch {
      status.text = "ERROR: \(error)"
    }
  }
}
