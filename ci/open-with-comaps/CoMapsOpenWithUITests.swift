import XCTest

// Private integration prototype. Compile this into the existing generated UI
// test bundle, whose target application remains GPXFixtures, not CoMaps.
@MainActor
final class CoMapsOpenWithUITests: XCTestCase {
  private let files = XCUIApplication(bundleIdentifier: "com.apple.DocumentsApp")
  private let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
  private var comaps: XCUIApplication?
  private var bundleID = ""
  private var displayName = ""
  private var expectedSourceURLs: [String: String] = [:]
  private var phase = "setup"

  private struct Fixture {
    let stem: String
    let category: String
    let track: String
  }

  private let cold = Fixture(stem: "Cold", category: "CoMaps Open With cold", track: "Cold imported track")
  private let warm = Fixture(stem: "Warm", category: "CoMaps Open With warm", track: "Warm imported track")
  private let successMessage = "Favorites loaded successfully! You can find them on the map or on the Favorites Manager screen."

  override func setUpWithError() throws {
    continueAfterFailure = false
  }

  override func tearDownWithError() throws {
    snapshot("final-\(phase)")
    try super.tearDownWithError()
  }

  // Breaks caught: missing Files handler registration; a dropped cold/warm
  // scene URL; failure to read the provider URL; missing or duplicate import.
  // Original bytes/mtime are checked independently by the host-side runner.
  func testFilesOpenWithImportsIntoActualCoMapsWhenColdAndWarm() throws {
    let environment = ProcessInfo.processInfo.environment
    bundleID = try XCTUnwrap(environment["COMAPS_BUNDLE_ID"], "HARNESS_MISSING_COMAPS_BUNDLE_ID")
    displayName = try XCTUnwrap(environment["COMAPS_DISPLAY_NAME"], "HARNESS_MISSING_COMAPS_DISPLAY_NAME")
    XCTAssertFalse(bundleID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
    XCTAssertFalse(displayName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
    XCTAssertNotEqual(bundleID, "org.comaps.diagnostic.gpxfixtures")
    XCTAssertNotEqual(bundleID, "org.comaps.diagnostic.gpxprobe")
    for (stem, key) in [("Cold", "COMAPS_COLD_SOURCE_URL"), ("Warm", "COMAPS_WARM_SOURCE_URL")] {
      let value = try XCTUnwrap(environment[key], "HARNESS_MISSING_EXPECTED_SOURCE_URL")
      let url = try XCTUnwrap(URL(string: value), "HARNESS_INVALID_EXPECTED_SOURCE_URL")
      XCTAssertTrue(url.isFileURL && url.lastPathComponent == stem + ".gpx", "HARNESS_WRONG_EXPECTED_SOURCE_URL")
      expectedSourceURLs[stem] = value
    }
    let app = XCUIApplication(bundleIdentifier: bundleID)
    comaps = app

    // The runner sets the whole fresh simulator to English. No -IsTests,
    // onboarding-default override, URL injection, or TCC database modification.
    app.launch()
    XCTAssertTrue(app.wait(for: .runningForeground, timeout: 30), "HARNESS_COMAPS_BOOTSTRAP_FAILED")
    waitForVisible(app.buttons["Favorites"], timeout: 30, failure: "HARNESS_MAP_NOT_READY")
    openFavorites(in: app)
    for fixture in [cold, warm] {
      XCTAssertEqual(categoryRows(in: app, prefix: fixture.category).count, 0, "HARNESS_STALE_IMPORT")
    }
    back(in: app, from: "Favorites", to: "Map")
    waitForVisible(app.buttons["Favorites"], failure: "HARNESS_MAP_NOT_READY")
    snapshot("bootstrap-ready")

    phase = "cold"
    app.terminate()
    XCTAssertTrue(app.wait(for: .notRunning, timeout: 15), "HARNESS_COMAPS_DID_NOT_TERMINATE")
    openFromFiles(cold, into: app, expectedCold: true)
    verifyImport(in: app, fixture: cold, imported: [cold])
    XCTAssertEqual(categoryRows(in: app, prefix: warm.category).count, 0, "UNEXPECTED_WARM_IMPORT")
    back(in: app, from: "Favorites", to: "Map")
    waitForVisible(app.buttons["Favorites"], failure: "HARNESS_MAP_NOT_READY_AFTER_COLD")

    phase = "warm"
    // Files activation backgrounds the same running CoMaps process. No second
    // app.launch(), app.activate(), terminate(), or URL injection is permitted.
    openFromFiles(warm, into: app, expectedCold: false)
    verifyImport(in: app, fixture: warm, imported: [cold, warm])
    assertTrack(in: app, fixture: cold) // The earlier import remains intact.
    attachJSON(["bundleID": bundleID, "verifiedImportCount": 2,
                "cold": ["category": cold.category, "track": cold.track],
                "warm": ["category": warm.category, "track": warm.track]],
               named: "comaps-import-observation")
    snapshot("both-imports-verified")
  }

  private func openFromFiles(_ fixture: Fixture, into app: XCUIApplication, expectedCold: Bool) {
    files.activate()
    XCTAssertTrue(files.wait(for: .runningForeground, timeout: 15), "HARNESS_FILES_NOT_FOREGROUND")
    dismissKeyboardIntroduction()
    navigateToFixtureFolder()
    dismissKeyboardIntroduction()
    let item = fixtureElement(stem: fixture.stem)
    XCTAssertTrue(item.waitForExistence(timeout: 10) && item.isHittable, "HARNESS_FIXTURE_NOT_VISIBLE: \(fixture.stem)")
    snapshot("\(phase)-fixture-in-files")
    item.press(forDuration: 1.2)
    if dismissKeyboardIntroduction() {
      // The observed introduction may dismiss the underlying file menu too.
      // Reopen only the same fixture, and only after that exact introduction.
      if !files.descendants(matching: .any).matching(NSPredicate(format: "label == %@", "Open With")).firstMatch.exists {
        item.press(forDuration: 1.2)
      }
    }
    tapFilesLabel("Open With")
    let handler = files.descendants(matching: .any).matching(
      NSPredicate(format: "label == %@ OR label == %@", displayName, "Open in " + displayName)
    ).firstMatch
    let present = handler.waitForExistence(timeout: 10)
    snapshot("\(phase)-open-with-menu")
    XCTAssertTrue(present, "COMAPS_OPEN_WITH_HANDLER_MISSING")
    XCTAssertTrue(handler.isHittable, "HARNESS_COMAPS_HANDLER_NOT_HITTABLE")

    // Capture/check immediately before the actual menu tap, rather than only
    // before navigating Files: iOS may have killed a background app meanwhile.
    let state = app.state
    attachJSON(["phase": phase, "filename": fixture.stem + ".gpx",
                "bundleID": bundleID, "displayName": displayName,
                "expectedSourceURL": expectedSourceURLs[fixture.stem]!,
                "stateBeforeTap": stateName(state), "stateRawValue": state.rawValue,
                "expectedCold": expectedCold],
               named: "\(phase)-process-before-handoff")
    if expectedCold {
      XCTAssertEqual(state, .notRunning, "HARNESS_COLD_PRECONDITION_FAILED")
    } else {
      XCTAssertTrue(state == .runningBackground || state == .runningBackgroundSuspended,
                    "HARNESS_WARM_PROCESS_WAS_NOT_ALIVE")
    }
    handler.tap()
    // Do not activate/launch CoMaps here: that could conceal failed delivery.
    XCTAssertTrue(app.wait(for: .runningForeground, timeout: 30), "COMAPS_NOT_OPENED_BY_FILES")
    snapshot("\(phase)-foreground-after-handoff")
  }

  private func verifyImport(in app: XCUIApplication, fixture: Fixture, imported: [Fixture]) {
    // MWMAlertViewController presents a custom view, not a UIKit UIAlertController.
    let success = app.staticTexts[successMessage]
    waitForVisible(success, timeout: 45, failure: "COMAPS_IMPORT_SUCCESS_MISSING")
    snapshot("\(phase)-import-success")
    let ok = app.buttons["OK"]
    XCTAssertTrue(ok.exists && ok.isHittable, "HARNESS_IMPORT_OK_MISSING")
    ok.tap()
    XCTAssertTrue(success.waitForNonExistence(timeout: 10), "HARNESS_IMPORT_DIALOG_NOT_DISMISSED")
    openFavorites(in: app)
    for item in imported {
      let rows = categoryRows(in: app, prefix: item.category)
      XCTAssertTrue(rows.firstMatch.waitForExistence(timeout: 10), "IMPORTED_CATEGORY_MISSING: \(item.category)")
      // Prefix also catches a duplicate category renamed with a numeric suffix.
      XCTAssertEqual(rows.count, 1, "IMPORTED_CATEGORY_DUPLICATED: \(item.category)")
      XCTAssertEqual(app.tables.cells.containing(.staticText, identifier: item.category).count, 1,
                     "IMPORTED_CATEGORY_NAME_DIFFERS")
    }
    snapshot("\(phase)-category-inventory")
    assertTrack(in: app, fixture: fixture)
  }

  private func assertTrack(in app: XCUIApplication, fixture: Fixture) {
    let category = app.tables.cells.containing(.staticText, identifier: fixture.category).firstMatch
    XCTAssertTrue(category.exists && category.isHittable, "HARNESS_CATEGORY_NOT_HITTABLE")
    category.tap()
    XCTAssertTrue(app.navigationBars[fixture.category].waitForExistence(timeout: 10), "HARNESS_CATEGORY_NOT_OPENED")
    let tracks = app.tables.cells.containing(.staticText, identifier: fixture.track)
    XCTAssertTrue(tracks.firstMatch.waitForExistence(timeout: 10), "IMPORTED_TRACK_MISSING: \(fixture.track)")
    XCTAssertEqual(tracks.count, 1, "IMPORTED_TRACK_DUPLICATED: \(fixture.track)")
    let prefixedTracks = app.tables.cells.containing(
      NSPredicate(format: "elementType == %d AND label BEGINSWITH %@", XCUIElement.ElementType.staticText.rawValue, fixture.track)
    )
    XCTAssertEqual(prefixedTracks.count, 1, "IMPORTED_TRACK_DUPLICATED_OR_RENAMED")
    snapshot("\(phase)-\(fixture.stem)-track-verified")
    back(in: app, from: fixture.category, to: "Favorites")
    XCTAssertTrue(app.navigationBars["Favorites"].waitForExistence(timeout: 10), "HARNESS_FAVORITES_NOT_RESTORED")
  }

  private func categoryRows(in app: XCUIApplication, prefix: String) -> XCUIElementQuery {
    app.tables.cells.containing(
      NSPredicate(format: "elementType == %d AND label BEGINSWITH %@", XCUIElement.ElementType.staticText.rawValue, prefix)
    )
  }

  private func openFavorites(in app: XCUIApplication) {
    let button = app.buttons["Favorites"]
    waitForVisible(button, failure: "HARNESS_FAVORITES_BUTTON_MISSING")
    button.tap()
    XCTAssertTrue(app.navigationBars["Favorites"].waitForExistence(timeout: 10), "HARNESS_FAVORITES_NOT_OPENED")
  }

  private func back(in app: XCUIApplication, from title: String, to previousTitle: String) {
    let bar = app.navigationBars[title]
    XCTAssertTrue(bar.exists, "HARNESS_UNEXPECTED_NAVIGATION_SCREEN: \(title)")
    let button = bar.buttons.matching(NSPredicate(format: "label == %@ OR label == %@", "Back", previousTitle)).firstMatch
    XCTAssertTrue(button.waitForExistence(timeout: 5) && button.isHittable, "HARNESS_BACK_BUTTON_MISSING: \(title)")
    button.tap()
  }

  // Deliberately isolated: align only this helper with the independently
  // observed Files probe before wiring this prototype into CI.
  private func navigateToFixtureFolder() {
    if files.navigationBars["GPX Fixtures"].exists { return }
    let browse = files.tabBars.buttons["Browse"]
    if browse.waitForExistence(timeout: 5) && browse.isHittable { browse.tap() }
    if files.navigationBars["GPX Fixtures"].exists { return }
    tapFilesLabel("On My iPhone")
    tapFilesLabel("GPX Fixtures")
    XCTAssertTrue(files.navigationBars["GPX Fixtures"].waitForExistence(timeout: 10), "HARNESS_WRONG_FIXTURE_FOLDER")
  }

  private func fixtureElement(stem: String) -> XCUIElement {
    let labels = NSPredicate(format: "label == %@ OR label == %@", stem, stem + ".gpx")
    let text = files.staticTexts.matching(labels).firstMatch
    if text.waitForExistence(timeout: 5) { return text }
    // Files can expose a summary label on the cell rather than a text child.
    return files.cells.matching(NSPredicate(format: "label == %@ OR label == %@ OR label BEGINSWITH %@ OR label BEGINSWITH %@",
                                          stem, stem + ".gpx", stem + ",", stem + ".gpx,")).firstMatch
  }

  private func tapFilesLabel(_ label: String) {
    let element = files.descendants(matching: .any).matching(NSPredicate(format: "label == %@", label)).firstMatch
    XCTAssertTrue(element.waitForExistence(timeout: 10) && element.isHittable, "HARNESS_FILES_ELEMENT_MISSING: \(label)")
    element.tap()
  }

  @discardableResult
  private func dismissKeyboardIntroduction() -> Bool {
    let introduction = files.staticTexts["Speed up your typing by sliding your finger across the letters to compose a word."]
    guard introduction.exists else { return false }
    snapshot("\(phase)-keyboard-introduction")
    let button = files.buttons["Continue"]
    XCTAssertTrue(button.exists && button.isHittable, "HARNESS_KEYBOARD_INTRODUCTION_NOT_DISMISSIBLE")
    button.tap()
    let dismissed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: introduction)
    XCTAssertEqual(XCTWaiter.wait(for: [dismissed], timeout: 10), .completed, "HARNESS_KEYBOARD_INTRODUCTION_REMAINS")
    return true
  }

  private func waitForVisible(_ element: XCUIElement, timeout: TimeInterval = 15, failure: String) {
    let deadline = Date().addingTimeInterval(timeout)
    repeat {
      handleStandardLocationPromptIfPresent()
      if element.waitForExistence(timeout: 1) && element.isHittable { return }
    } while Date() < deadline
    snapshot("failure-\(phase)")
    XCTFail(failure)
  }

  private func handleStandardLocationPromptIfPresent() {
    let alert = springboard.alerts.firstMatch
    guard alert.exists else { return }
    let text = ([alert.label] + alert.staticTexts.allElementsBoundByIndex.map(\.label)).joined(separator: " ")
    guard text.localizedCaseInsensitiveContains("location"),
          text.contains(displayName) || text.contains("CoMaps") else { return }
    let deny = alert.buttons.matching(
      NSPredicate(format: "label == %@ OR label == %@", "Don’t Allow", "Don't Allow")
    ).firstMatch
    guard deny.exists && deny.isHittable else { return }
    snapshot("\(phase)-standard-location-prompt")
    // File import needs no location access. Deny through the ordinary prompt;
    // never grant a private permission or modify the simulator's TCC database.
    deny.tap()
  }

  private func snapshot(_ name: String) {
    let screen = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
    screen.name = name
    screen.lifetime = .keepAlways
    add(screen)
    attachText(files.debugDescription, named: name + "-files-accessibility")
    if let app = comaps, app.state != .notRunning {
      attachText(app.debugDescription, named: name + "-comaps-accessibility")
    }
  }

  private func attachJSON(_ value: [String: Any], named name: String) {
    do {
      let data = try JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys])
      attachText(String(decoding: data, as: UTF8.self), named: name)
    } catch {
      XCTFail("HARNESS_EVIDENCE_ENCODING_FAILED: \(error)")
    }
  }

  private func stateName(_ state: XCUIApplication.State) -> String {
    switch state {
    case .notRunning: return "notRunning"
    case .runningBackground: return "runningBackground"
    case .runningBackgroundSuspended: return "runningBackgroundSuspended"
    case .runningForeground: return "runningForeground"
    default: return "unknown"
    }
  }

  private func attachText(_ text: String, named name: String) {
    let attachment = XCTAttachment(string: text)
    attachment.name = name
    attachment.lifetime = .keepAlways
    add(attachment)
  }
}
