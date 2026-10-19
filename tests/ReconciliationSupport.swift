import Foundation
import Darwin

enum PipelineLogLevel { case info, error, debug, warning }
func LOG<T>(_ level: PipelineLogLevel, _ message: T) {}
func L(_ key: String) -> String { key }

// The Foundation harness has no CoreApi. Native map_tests exercise this boundary in the real core.
enum IncomingCategoryResult { case applied, skipped, failed }

final class PipelineStore: SynchronizedStateStore {
  var states = [String: SynchronizedFileState]()
  func state(for fileName: String) -> SynchronizedFileState? { states[fileName] }
  func setState(_ state: SynchronizedFileState?, for fileName: String) { states[fileName] = state }
  func resetIfCloudIdentityChanged(_ identity: Data) { states.removeAll() }
}

final class PipelineClock: SynchronizationClock { var activeTime: TimeInterval = 0 }
