import Foundation

let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true).standardizedFileURL
try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
let a = Data("<kml><Document><name>Collection A</name></Document></kml>".utf8)
let b = Data("<kml><Document><name>Collection B</name></Document></kml>".utf8)
let c = Data("<kml><Document><name>Collection C</name></Document></kml>".utf8)

func require(_ value: Bool, _ message: String) {
  precondition(value, message)
}

final class FileCase {
  let localDir: URL
  let cloudDir: URL
  let localURL: URL
  let cloudURL: URL
  let store = PipelineStore()
  let clock = PipelineClock()
  let provider = FileContentFingerprintProvider()
  let writer: SynchronizationFileWriter
  lazy var resolver = iCloudSynchronizationStateResolver(store: store, fingerprintProvider: provider, clock: clock)

  init(_ name: String, local: Data, cloud: Data, base: Data? = nil) throws {
    let directory = root.appendingPathComponent(name, isDirectory: true)
    localDir = directory.appendingPathComponent("local", isDirectory: true)
    cloudDir = directory.appendingPathComponent("cloud", isDirectory: true)
    localURL = localDir.appendingPathComponent("Collection.kml")
    cloudURL = cloudDir.appendingPathComponent("Collection.kml")
    try FileManager.default.createDirectory(at: localDir, withIntermediateDirectories: true)
    try FileManager.default.createDirectory(at: cloudDir, withIntermediateDirectories: true)
    try local.write(to: localURL)
    try cloud.write(to: cloudURL)
    try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSince1970: 200)], ofItemAtPath: localURL.path)
    try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSince1970: 100)], ofItemAtPath: cloudURL.path)
    writer = SynchronizationFileWriter(localDirectoryUrl: localDir, cloudDirectoryUrl: cloudDir)
    if let base {
      store.setState(SynchronizedFileState(fingerprint: Fingerprint(hashing: base)), for: "Collection.kml")
    }
  }

  func cloudItem(at url: URL? = nil) throws -> CloudMetadataItem {
    let item = LocalMetadataItem(fileUrl: url ?? cloudURL)!
    return CloudMetadataItem(fileName: item.fileName, fileUrl: item.fileUrl,
                             lastModificationDate: item.lastModificationDate, size: item.size,
                             isDownloaded: true, hasUnresolvedConflicts: false,
                             downloadingError: nil, uploadingError: nil)
  }

  func decisions(cloudAt url: URL? = nil) throws -> [OutgoingSynchronizationEvent] {
    var events = [OutgoingSynchronizationEvent]()
    provider.onContentsMayBeKnown = { [weak self] in
      guard let self else { return }
      events += resolver.resolveEvent(.didUpdateKnownContents)
    }
    events += resolver.resolveEvent(.didUpdateLocalContents(LocalSnapshot(items: [LocalMetadataItem(fileUrl: localURL)!])))
    events += resolver.resolveEvent(.didUpdateCloudContents(CloudSnapshot(items: [try cloudItem(at: url)])))
    wait { !events.isEmpty || self.store.state(for: "Collection.kml") != nil &&
      self.provider.fingerprint(of: LocalMetadataItem(fileUrl: self.localURL)!) != nil &&
      self.provider.fingerprint(of: try! self.cloudItem(at: url)) != nil }
    provider.onContentsMayBeKnown = nil
    return events
  }

  func process(_ events: [OutgoingSynchronizationEvent], beforeInstall: (() throws -> Void)? = nil) throws -> [String] {
    var completed = 0
    var outcomes = [String]()
    var errors = [String]()
    for event in events {
      writer.processEvent(event) { result in
        switch result {
        case .applyIncomingCategory(let snapshot):
          do {
            try beforeInstall?()
            // Only the file adapter is synthetic; staging, hashing, coordination and final feedback are production.
            guard snapshot.destinationMatchesExpected(snapshot.targetURL.path) else {
              snapshot.finish(.skipped)
              return
            }
            let status = snapshot.fileURL.path.withCString { source in
              snapshot.targetURL.path.withCString { destination in Darwin.rename(source, destination) }
            }
            snapshot.finish(status == 0 ? .applied : .failed)
          } catch { errors.append(String(describing: error)); snapshot.finish(.failed) }
        case .written(let content):
          outcomes.append("written")
          self.resolver.resolveEvent(.didFinishWriting(event, writtenContent: content))
          completed += 1
        case .skipped:
          outcomes.append("skipped")
          self.resolver.resolveEvent(.didFailWriting(event))
          completed += 1
        case .failure(let error):
          errors.append(String(describing: error))
          self.resolver.resolveEvent(.didFailWriting(event))
          completed += 1
        default:
          errors.append("Unexpected operation in file transfer fixture")
          completed += 1
        }
      }
    }
    wait { completed == events.count }
    require(errors.isEmpty, "Writer failure: \(errors)")
    return outcomes
  }

  func copies() throws -> [URL] {
    try FileManager.default.contentsOfDirectory(at: localDir, includingPropertiesForKeys: nil)
      .filter { $0.pathExtension == "kml" && $0.lastPathComponent != localURL.lastPathComponent }
  }
}

func wait(_ finished: () -> Bool) {
  let deadline = Date().addingTimeInterval(10)
  while !finished(), Date() < deadline {
    _ = RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.01))
  }
  require(finished(), "Timed out waiting for a production callback")
}

var results = [[String: Any]]()
func scenario(_ name: String, _ body: () throws -> Void) rethrows {
  try body()
  results.append(["case": name, "passed": true])
}

try scenario("equal-bytes-different-dates") {
  let test = try FileCase("equal", local: a, cloud: a)
  require(try test.decisions().isEmpty, "Equal content requested a transfer")
  require(try test.copies().isEmpty, "Equal content created a copy")
  require(test.store.state(for: "Collection.kml")?.fingerprint == Fingerprint(hashing: a), "Equal content did not establish the base")
}
try scenario("equal-bytes-existing-copy") {
  let test = try FileCase("existing", local: a, cloud: a)
  let copy = test.localDir.appendingPathComponent("Collection_1.kml")
  try b.write(to: copy)
  require(try test.decisions().isEmpty, "Equal content requested a transfer")
  require(try Data(contentsOf: copy) == b, "Existing copy was modified")
  require(try test.copies().count == 1, "An extra copy appeared")
}
try scenario("unknown-base-preserves-different-local-version") {
  let test = try FileCase("no-base", local: a, cloud: b)
  require(try test.process(test.decisions()) == ["written"], "Incoming file was not installed")
  require(try Data(contentsOf: test.localURL) == b, "Cloud content not installed")
  let copies = try test.copies()
  require(try copies.count == 1 && Data(contentsOf: copies[0]) == a, "Unsynchronized local content lost")
}
try scenario("local-only-edit-uploads-without-copy") {
  let test = try FileCase("local-edit", local: b, cloud: a, base: a)
  require(try test.process(test.decisions()) == ["written"], "Local edit not uploaded")
  require(try Data(contentsOf: test.cloudURL) == b, "Cloud content is stale")
  require(try test.copies().isEmpty, "One-sided edit created a copy")
}
try scenario("remote-only-edit-downloads-without-copy") {
  let test = try FileCase("remote-edit", local: a, cloud: b, base: a)
  require(try test.process(test.decisions()) == ["written"], "Remote edit not installed")
  require(try Data(contentsOf: test.localURL) == b, "Local content is stale")
  require(try test.copies().isEmpty, "One-sided edit created a copy")
}
try scenario("concurrent-edits-preserve-local-then-repeat-does-not-duplicate") {
  let test = try FileCase("concurrent", local: b, cloud: c, base: a)
  require(try test.process(test.decisions()) == ["written"], "Conflict not installed")
  require(try Data(contentsOf: test.localURL) == c, "Cloud version lost")
  let copies = try test.copies()
  require(try copies.count == 1 && Data(contentsOf: copies[0]) == b, "Local version lost")
  test.resolver = iCloudSynchronizationStateResolver(store: test.store, fingerprintProvider: test.provider, clock: test.clock)
  require(try test.decisions().isEmpty, "A restarted resolver repeated the conflict")
  require(try test.copies().count == 1, "The conflict copy was duplicated")
}
try scenario("metadata-only-difference-remains-a-conflict-without-base") {
  let x = Data("<kml><Document><name>A</name><ExtendedData><lastModified>2026-10-01</lastModified></ExtendedData></Document></kml>".utf8)
  let y = Data("<kml><Document><name>A</name><ExtendedData><lastModified>2026-10-02</lastModified></ExtendedData></Document></kml>".utf8)
  let test = try FileCase("metadata", local: x, cloud: y)
  require(try test.process(test.decisions()) == ["written"], "Byte-different content not installed")
  require(try Data(contentsOf: test.localURL) == y, "Actual cloud content not installed")
  let copies = try test.copies()
  require(try copies.count == 1 && Data(contentsOf: copies[0]) == x, "Byte-different local version lost")
}
try scenario("transfer-uses-actual-cloud-metadata-url") {
  let test = try FileCase("metadata-url", local: a, cloud: a)
  let directory = test.cloudDir.appendingPathComponent("moved", isDirectory: true)
  try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
  let moved = directory.appendingPathComponent("Collection.kml")
  try b.write(to: moved)
  require(try test.process(test.decisions(cloudAt: moved)) == ["written"], "Metadata URL transfer not installed")
  require(try Data(contentsOf: test.localURL) == b, "Transferred a different file than the one compared")
}
try scenario("vanished-source-keeps-local-file") {
  let test = try FileCase("vanished", local: a, cloud: b)
  let events = try test.decisions()
  try FileManager.default.removeItem(at: test.cloudURL)
  require(try test.process(events) == ["skipped"], "A vanished source was accepted")
  require(try Data(contentsOf: test.localURL) == a, "Local version lost")
  require(try test.copies().isEmpty, "Failed transfer left a conflict copy")
}
try scenario("destination-changed-after-decision-is-not-overwritten") {
  let test = try FileCase("changed-destination", local: a, cloud: b)
  let events = try test.decisions()
  require(try test.process(events, beforeInstall: { try c.write(to: test.localURL) }) == ["skipped"], "New local content was accepted for replacement")
  require(try Data(contentsOf: test.localURL) == c, "New local edit was overwritten")
  require(try test.copies().isEmpty, "Skipped transfer left an unused copy")
  require(test.store.state(for: "Collection.kml") == nil, "Skipped transfer established a false base")
}
try scenario("source-changed-after-decision-records-installed-bytes") {
  let test = try FileCase("changed-source", local: a, cloud: b, base: a)
  let events = try test.decisions()
  try c.write(to: test.cloudURL)
  require(try test.process(events) == ["written"], "Changed source content not installed")
  require(try Data(contentsOf: test.localURL) == c, "Actual staged content not installed")
  require(test.store.state(for: "Collection.kml")?.fingerprint == Fingerprint(hashing: c), "The base describes stale source metadata")
}
try scenario("edited-hash-named-copy-is-preserved") {
  let test = try FileCase("edited-copy", local: b, cloud: c, base: a)
  let preferred = test.writer.copyUrl(of: test.localURL, holding: Fingerprint(hashing: b))
  try a.write(to: preferred)
  require(try test.process(test.decisions()) == ["written"], "Conflict not installed")
  require(try Data(contentsOf: test.localURL) == c, "Conflict cloud version not installed")
  require(try Data(contentsOf: preferred) == a, "An edited conflict copy was overwritten")
  let contents = try test.copies().map { try Data(contentsOf: $0) }
  require(contents.count == 2 && contents.contains(a) && contents.contains(b), "Concurrent local content lost")
}
let report: [String: Any] = ["mode": "candidate-full-reconciliation", "cases": results,
  "all_passed": true, "live_icloud_tested": false, "complete_duplicate_fix": false,
  "core_boundary": "synthetic file adapter; real core covered by native map_tests"]
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]))
print()
