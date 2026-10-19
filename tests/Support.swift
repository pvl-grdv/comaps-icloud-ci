import Foundation
import Darwin

enum TestLogLevel { case info, error, debug, warning }
func LOG<T>(_ level: TestLogLevel, _ message: T) {}
enum SynchronizationError: Error { case failedToCreateMetadataItem, fileUnavailable }
extension NSError { var ubiquitousError: SynchronizationError? { nil } }
struct UIDevice {
  static let current = UIDevice()
  let name = "SyntheticDevice"
}
enum WritingResult {
  case success
  case reloadCategoriesAtURLs([URL])
#if INCOMING_CATEGORY_SNAPSHOT
  case applyIncomingCategory(IncomingCategorySnapshot)
#endif
  case deleteCategoriesAtURLs([URL])
  case failure(Error)
}
typealias WritingResultCompletionHandler = (WritingResult) -> Void
