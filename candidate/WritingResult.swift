// Extracted unchanged from SynchronizaionManager.swift.
enum WritingResult {
  case success
  /// The fingerprint is computed from the staged copy that was installed, rather than from a snapshot of its source.
  case written(Fingerprint)
  /// Nothing was written because what the operation assumed is not true anymore. It is not a failure and not a
  /// success either: the file is reconciled again from what is observed next.
  case skipped(String)
  case applyIncomingCategory(IncomingCategorySnapshot)
  /// Deletions are only requested by the writer: they are destructive and are authorized against the latest
  /// observations, on the queue where the synchronization state lives.
  case deleteCategory(atURL: URL)
  /// The expected content is verified once more, right before the file leaves the synchronized directory.
  case trashCloudItem(atURL: URL, expecting: Fingerprint)
  case failure(Error)
}

typealias WritingResultCompletionHandler = (WritingResult) -> Void

