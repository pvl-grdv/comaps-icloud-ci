04-saved-items-search: Поиск точек и треков

AI-assisted техническая карточка для личного разбора CoMaps. Не готовый текст PR.

Проблема и результат
Общий поиск и поиск внутри папки находят точки и треки. Типизированный ID различает точку и трек
с одинаковым числовым ID. Устаревшие ответы, отмена и удалённые результаты обрабатываются явно.

Границы
Описания поддерживаются ядром только при включённом флаге; iOS его не включает. Названия папок
не индексируются. Для точек есть оригинальные/пользовательские имена и типовые псевдонимы; у
треков используется предпочтительное локализованное имя. На большой реальной библиотеке
производительность не измерена.

Готовность
Независимый срез выделен: proposals/saved-items/search.patch
SHA-256: 3145ed99469a088305894e378c1132f9dc847c37ce9ab1a5db3ab9aa3267fb09
База: a64450d0c7cd7cdfc792c9fc6c2dd620156abecd
CI: https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/39582197192
Требуется: native map=1, search=11, XCTest=19 без пропусков, unsigned Release archive.
Текущий статус и точный проверенный SHA: ../../evidence/status.json. Общий зелёный Lab CI не
заменяет этот прогон.
Ни одна тема не опубликована в CoMaps.

Зависимости
Обязательных логических предпосылок нет; общие hunks всё равно нужно разделить.

Регрессии общего набора
bookmarks_processor_tests.cpp::BookmarksProcessorTest_Smoke
bookmarks_processor_tests.cpp::BookmarksProcessorTest_SearchByType
bookmarks_processor_tests.cpp::BookmarksProcessorTest_IndexDescriptions
bookmarks_processor_tests.cpp::SavedItemsIndexTest_CollidingNumericIds
bookmarks_processor_tests.cpp::SavedItemsIndexTest_UnicodePrefixAndDescription
bookmarks_processor_tests.cpp::SavedItemsIndexTest_SnapshotRenameMoveDeleteReload
bookmarks_processor_tests.cpp::SavedItemsIndexTest_InvalidSnapshotRetainsPreviousIndex
bookmarks_processor_tests.cpp::SavedItemsIndexTest_CancelledSearch
bookmarks_processor_tests.cpp::SavedItemsProcessorTest_CancelledBeforeProcessingCompletesTypedCallback
bookmarks_processor_tests.cpp::SavedItemsProcessorTest_CancelledLegacyRequestStillCompletes
bookmarks_processor_tests.cpp::SavedItemsIndexTest_OriginalAndCustomNamesSurviveUpdates
BMCSearchViewModelTests.testRepeatedStartAndStopPrepareAndReleaseOnlyOnce
BMCSearchViewModelTests.testResultsAreGroupedByCategoryIdentityInResultOrder
BMCSearchViewModelTests.testEarlierQueryCannotReplaceCurrentResults
BMCSearchViewModelTests.testDismissedSearchIgnoresPendingResults
BMCSearchViewModelTests.testClearingQueryClearsResultsAndInvalidatesOldCompletion
BMCSearchViewModelTests.testRefreshReindexesAndRepeatsCurrentQuery
BMCSearchViewModelTests.testInactiveRefreshDoesNotAcquireIndex
BMCSearchViewModelTests.testRestartDoesNotAcceptCompletionFromPreviousSession
BMCSearchViewModelTests.testSelectingDeletedResultRefreshesInsteadOfReturningStaleIdentity
BMCSearchViewModelTests.testBookmarkAndTrackWithSameNumericIdRemainDistinct
BMCSearchViewModelTests.testSelectingMovedResultUsesItsCurrentCategory
SavedItemsSearchTests.testTypedResultPreservesKindWithEqualNumericIds
SavedItemsSearchTests.testCurrentFolderSearchReturnsBothKindsFromOnlyThatFolder
SavedItemsSearchTests.testGlobalSearchIncludesBothFoldersAndBothKinds
SavedItemsSearchTests.testChildCollectionSearchUsesMembershipInsteadOfPrimaryParent
SavedItemsSearchTests.testRenamedTrackIsReplacedInTheNextSearchSnapshot
SavedItemsSearchTests.testMovedTrackLeavesOldScopeAndAppearsInNewScope
SavedItemsSearchTests.testDeletedTrackIsNotSearchableOrSelectable
SavedItemsSearchTests.testLegacyBookmarkSearchStillReturnsOnlyBookmarks
Точные source paths, границы с соседними темами и список файлов: ../../plan.json.
Полный текущий план166 XCTest и Local167 не означают, что каждый из8 срезов проверен самостоятельно.

Происхождение кода/идей
{
  "kind": "CoMaps-specific AI-assisted implementation"
}

Связанные запросы CoMaps (состояния — ../../README.txt)
https://codeberg.org/comaps/comaps/issues/4403
https://codeberg.org/comaps/comaps/pulls/4407

Исторические патчи (НЕ порядок применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/global-bookmark-search.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/typed-saved-items-search.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/typed-saved-items-ios.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/typed-search-cancellation.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/hosted-bookmarks-ui-smoke.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/search-viewport-test-setup.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/cancellation-test-explicit-catch.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/bookmark-original-name-search-alias.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/explicit-search-service-capture.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/hosted-ui-window-lifecycle.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/search-fixture-directory.patch

Поиск по названию самой папки или описанию в UI не заявляется. Перенос между папками —
существующая команда Move для точек и треков, а не наша новая функция.
