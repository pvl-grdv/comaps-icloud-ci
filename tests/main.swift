import Foundation

let mode = CommandLine.arguments[1]
let root = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
let same = Data("<kml><Document><name>Collection A</name></Document></kml>".utf8)
let other = Data("<kml><Document><name>Collection B</name></Document></kml>".utf8)

func runCase(_ caseName: String, localData: Data, cloudData: Data, preexistingCopy: Data? = nil, alternateCloudLocation: Bool = false, restoreCloudAfterConflict: Bool = false) throws -> [String: Any] {
  let caseRoot = root.appendingPathComponent(caseName, isDirectory: true)
  let localDir = caseRoot.appendingPathComponent("local", isDirectory: true)
  let cloudDir = caseRoot.appendingPathComponent("cloud", isDirectory: true)
  try FileManager.default.createDirectory(at: localDir, withIntermediateDirectories: true)
  try FileManager.default.createDirectory(at: cloudDir, withIntermediateDirectories: true)
  let localURL = localDir.appendingPathComponent("Collection.kml")
  let cloudURL = cloudDir.appendingPathComponent("Collection.kml")
  let backupURL = localDir.appendingPathComponent("Collection_1_SyntheticDevice.kml")
  try localData.write(to: localURL)
  try cloudData.write(to: cloudURL)
  var metadataCloudURL = cloudURL
  if alternateCloudLocation {
    let moved = cloudDir.appendingPathComponent("moved", isDirectory: true)
    try FileManager.default.createDirectory(at: moved, withIntermediateDirectories: true)
    metadataCloudURL = moved.appendingPathComponent("Collection.kml")
    try cloudData.write(to: metadataCloudURL)
    try localData.write(to: cloudURL)
  }
  try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSince1970: 200)], ofItemAtPath: localURL.path)
  try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSince1970: 100)], ofItemAtPath: cloudURL.path)
  if let preexistingCopy { try preexistingCopy.write(to: backupURL) }
  let localItem = try LocalMetadataItem(fileUrl: localURL)
  let cloudItem = CloudMetadataItem(fileName: "Collection.kml", fileUrl: metadataCloudURL,
    isDownloaded: true, percentDownloaded: 100, lastModificationDate: 100,
    downloadingError: nil, uploadingError: nil, hasUnresolvedConflicts: false)
  let resolver = iCloudSynchronizationStateResolver(isInitialSynchronization: true)
  _ = resolver.resolveEvent(.didFinishGatheringLocalContents([localItem]))
  let events = resolver.resolveEvent(.didFinishGatheringCloudContents([cloudItem]))
  if restoreCloudAfterConflict { try FileManager.default.removeItem(at: metadataCloudURL) }
  let writer = SynchronizationFileWriter(localDirectoryUrl: localDir, cloudDirectoryUrl: cloudDir)
  var completed = 0
  var failures: [String] = []
  for event in events {
    let isInitialConflict: Bool = { if case .resolveInitialSynchronizationConflict = event { return true }; return false }()
    writer.processEvent(event) { result in
      if isInitialConflict && restoreCloudAfterConflict {
        do { try cloudData.write(to: metadataCloudURL) } catch { failures.append(String(describing: error)) }
      }
#if INCOMING_CATEGORY_SNAPSHOT
      if case .applyIncomingCategory(let snapshot) = result {
        // File-pipeline harness only: native map_tests exercise the actual core entrypoint.
        // Acknowledge only after installing the staged bytes, preserving event ordering.
        defer { snapshot.finish() }
        let renamed = snapshot.fileURL.path.withCString { source in
          snapshot.targetURL.path.withCString { destination in Darwin.rename(source, destination) }
        }
        if renamed != 0 { failures.append("Synthetic incoming installation failed: \(errno)") }
      }
#endif
      if case .failure(let error) = result { failures.append(String(describing: error)) }
      completed += 1
    }
  }
  let deadline = Date().addingTimeInterval(10)
  while completed < events.count && Date() < deadline {
    _ = RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.01))
  }
  precondition(completed == events.count, "Timed out")
  precondition(failures.isEmpty, "Writer failure: \(failures)")
  let hasBackup = FileManager.default.fileExists(atPath: backupURL.path)
  let baseline = mode == "baseline"
  let expectBackup = preexistingCopy != nil || baseline || localData != cloudData
  precondition(hasBackup == expectBackup, "Unexpected conflict copy")
  let currentLocal = try Data(contentsOf: localURL)
  precondition(currentLocal == cloudData)
  if localData != cloudData {
    let saved = try Data(contentsOf: backupURL)
    precondition(saved == localData)
  }
  if let preexistingCopy, !baseline {
    let saved = try Data(contentsOf: backupURL)
    precondition(saved == preexistingCopy, "Existing copy changed for equal files")
  }
  return ["case": caseName, "passed": true, "conflict_copy_exists": hasBackup,
    "new_conflict_copy_created": hasBackup && preexistingCopy == nil,
    "local_and_cloud_bytes_equal_before": localData == cloudData,
    "preexisting_copy_preserved": preexistingCopy == nil ? NSNull() : ((try Data(contentsOf: backupURL)) == preexistingCopy!)]
}

var results: [[String: Any]] = []
results.append(try runCase("equal-bytes-different-dates", localData: same, cloudData: same))
results.append(try runCase("different-bytes", localData: same, cloudData: other))
results.append(try runCase("equal-bytes-existing-copy", localData: same, cloudData: same, preexistingCopy: other))
let datedA = Data("<kml><Document><name>A</name><ExtendedData><lastModified>2026-10-01</lastModified></ExtendedData></Document></kml>".utf8)
let datedB = Data("<kml><Document><name>A</name><ExtendedData><lastModified>2026-10-02</lastModified></ExtendedData></Document></kml>".utf8)
results.append(try runCase("metadata-only-difference-known-limitation", localData: datedA, cloudData: datedB))
results.append(try runCase("metadata-url-must-match-transferred-file", localData: same, cloudData: other, alternateCloudLocation: true))
results.append(try runCase("unavailable-comparison-preserves-local-data", localData: same, cloudData: other, restoreCloudAfterConflict: true))
let result: [String: Any] = ["mode": mode, "cases": results, "all_passed": true, "complete_duplicate_fix": false]
let encoded = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
FileHandle.standardOutput.write(encoded)
print()
