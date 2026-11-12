import CryptoKit
import XCTest

@MainActor
final class OpenWithUITests: XCTestCase {
  private let files = XCUIApplication(bundleIdentifier: "com.apple.DocumentsApp")
  private let fixtures = XCUIApplication(bundleIdentifier: "org.comaps.diagnostic.gpxfixtures")
  private let probe = XCUIApplication(bundleIdentifier: "org.comaps.diagnostic.gpxprobe")
  private let control = XCUIApplication(bundleIdentifier: "org.comaps.diagnostic.gpxcontrol")

  override func setUpWithError() throws {
    continueAfterFailure = false
  }

  override func tearDownWithError() throws {
    attachScreen("final-screen")
    attachText(files.debugDescription, named: "files-final-accessibility")
    try super.tearDownWithError()
  }

  func testFilesOpenWithEligibilityAndDelivery() throws {
    let data = try Data(contentsOf: XCTUnwrap(Bundle(for: type(of: self)).url(forResource: "Fixture", withExtension: "gpx")))
    let expectedHash = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    for app in [probe, control, fixtures] {
      app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
      app.launch()
      XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10), "HARNESS_APP_DID_NOT_LAUNCH")
    }
    let initial = try status(fixtures.staticTexts["fixtureStatus"])
    XCTAssertEqual(initial["sha256"] as? String, expectedHash, "HARNESS_FIXTURE_HASH_MISMATCH")

    files.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
    files.launch()
    XCTAssertTrue(files.wait(for: .runningForeground, timeout: 10), "HARNESS_FILES_DID_NOT_LAUNCH")
    let browse = files.tabBars.buttons["Browse"]
    if browse.waitForExistence(timeout: 5) { browse.tap() }
    try tap(label: "On My iPhone")
    try tap(label: "GPX Fixtures")
    let fixture = files.cells.matching(NSPredicate(format: "label CONTAINS %@", "OpenWithProbe")).firstMatch
    let fixtureText = files.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "OpenWithProbe")).firstMatch
    let item = fixture.waitForExistence(timeout: 5) ? fixture : fixtureText
    XCTAssertTrue(item.waitForExistence(timeout: 5) && item.isHittable, "HARNESS_FIXTURE_NOT_VISIBLE")
    attachScreen("fixture-in-files")
    item.press(forDuration: 1.2)
    try tap(label: "Open With")
    let controlEntry = namedHandler("GPX Control")
    XCTAssertTrue(controlEntry.waitForExistence(timeout: 5) && controlEntry.isHittable,
                  "HARNESS_POSITIVE_CONTROL_MISSING")
    attachScreen("open-with-menu")
    attachText(files.debugDescription, named: "open-with-menu-accessibility")
    let probeEntry = namedHandler("GPX Probe")
    let visible = probeEntry.waitForExistence(timeout: 3)
    attachText("{\"controlPresent\":true,\"receiverPresent\":\(visible)}", named: "open-with-observation")

    // IDENTICAL assertion in both variants. Only this normal assertion failure
    // is accepted as the NO-arm negative control; navigation failures are not.
    XCTAssertTrue(visible, "OPEN_WITH_RECEIVER_MISSING")
    XCTAssertTrue(probeEntry.isHittable, "HARNESS_RECEIVER_NOT_HITTABLE")
    probeEntry.tap()
    XCTAssertTrue(probe.wait(for: .runningForeground, timeout: 10), "RECEIVER_WAS_NOT_OPENED")
    let receipt = try status(probe.staticTexts["receipt"])
    attachText(String(data: try JSONSerialization.data(withJSONObject: receipt, options: [.sortedKeys]), encoding: .utf8)!,
               named: "receiver-receipt")
    attachScreen("receiver-after-open-with")
    XCTAssertEqual(receipt["filename"] as? String, "OpenWithProbe.gpx")
    XCTAssertEqual(receipt["readSucceeded"] as? Bool, true, "RECEIVER_COULD_NOT_READ")
    XCTAssertEqual(receipt["openInPlace"] as? Bool, true, "RECEIVER_DID_NOT_RECEIVE_OPEN_IN_PLACE")
    XCTAssertEqual(receipt["sha256"] as? String, expectedHash, "RECEIVER_BYTES_DIFFER")
    XCTAssertEqual(receipt["bytes"] as? Int, data.count)
    XCTAssertNil(receipt["error"])
    fixtures.activate()
    XCTAssertTrue(fixtures.wait(for: .runningForeground, timeout: 10))
    let final = try status(fixtures.staticTexts["fixtureStatus"])
    XCTAssertEqual(final["sha256"] as? String, expectedHash, "ORIGINAL_FILE_CHANGED")
    XCTAssertEqual(final["bytes"] as? Int, data.count)
    attachText(String(data: try JSONSerialization.data(withJSONObject: final, options: [.sortedKeys]), encoding: .utf8)!,
               named: "source-after-receipt")
  }

  private func namedHandler(_ name: String) -> XCUIElement {
    files.descendants(matching: .any).matching(NSPredicate(format: "label == %@ OR label == %@", name, "Open in " + name)).firstMatch
  }

  private func tap(label: String) throws {
    let element = files.descendants(matching: .any).matching(NSPredicate(format: "label == %@", label)).firstMatch
    XCTAssertTrue(element.waitForExistence(timeout: 10) && element.isHittable, "HARNESS_MENU_ELEMENT_MISSING: \(label)")
    element.tap()
  }

  private func status(_ label: XCUIElement) throws -> [String: Any] {
    let ready = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == true AND label BEGINSWITH %@", "{"), object: label)
    XCTAssertEqual(XCTWaiter.wait(for: [ready], timeout: 10), .completed, "HARNESS_RECEIPT_NOT_READY")
    return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(label.label.utf8)) as? [String: Any])
  }

  private func attachScreen(_ name: String) {
    let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
    attachment.name = name
    attachment.lifetime = .keepAlways
    add(attachment)
  }

  private func attachText(_ text: String, named name: String) {
    let attachment = XCTAttachment(string: text)
    attachment.name = name
    attachment.lifetime = .keepAlways
    add(attachment)
  }
}
