06-manual-item-order: Ручной порядок точек и треков

AI-assisted техническая карточка для личного разбора CoMaps. Не готовый текст PR.

Проблема и результат
Внутри папки точки и треки остаются в отдельных разделах. Полный корректный порядок сохраняется
в KML через comaps:itemOrder и comaps:itemSorting; добавление, перенос, удаление и undo
учитывают ранги. Верхняя Edit включает ручную перестановку, Done завершает её; прежний Sort →
Edit убран. Кнопки удаления сохранены, сессия перестановки завершается до удаления.

Границы
Смешанный список точек и треков не реализован. Две конфликтующие KML-версии не сливаются по
отдельным рангам. JNI fallback сохраняет совместимость, но Android UI ручного порядка не
добавлен. Отдельной регрессии доставки уже поставленного в очередь autosort-callback после reset
в плане нет. Снимки HostedBookmarksUISmokeTests не показывают экран/жест перестановки точек и
треков; это остаётся ручной проверкой. Отдельная Android-сборка JNI-изменений не подтверждена.

Готовность
Независимый срез выделен: proposals/saved-items/item-order.patch
SHA-256: ab294976fc4d8a32f3cf318444c83d2bfbfeb617dead32abe17f2b693cf2482a
База: a64450d0c7cd7cdfc792c9fc6c2dd620156abecd
CI: https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/39581652809
Требуется: native map=8, search=0, XCTest=13 без пропусков, unsigned Release archive.
Текущий статус и точный проверенный SHA: ../../evidence/status.json. Общий зелёный Lab CI не
заменяет этот прогон.
Ни одна тема не опубликована в CoMaps.

Зависимости
Обязательных логических предпосылок нет; общие hunks всё равно нужно разделить.

Регрессии общего набора
ManualItemOrder_PersistenceAfterReload
ManualItemOrder_RejectsStaleForeignAndDuplicateIds
ManualItemOrder_InvalidRanksAndNewItems
ManualItemOrder_SharedModeAndDefault
ManualItemOrder_AppendsNewMovedItemsAndHandlesDeletion
ManualItemOrder_AppendsNormallyCreatedBookmarks
ManualItemOrder_UndoKeepsOriginalBookmarkPosition
BookmarkItemOrderModelTests.testMovingBookmarkLeavesTrackSequenceUnchanged
BookmarkItemOrderModelTests.testMovingTrackLeavesBookmarkSequenceUnchanged
BookmarkItemOrderModelTests.testEqualNumericIdsInDifferentSectionsRemainDistinct
BookmarkItemOrderModelTests.testInvalidMoveDoesNotChangeEitherSequence
BookmarkItemOrderModelTests.testDuplicateIdsWithinEitherSectionAreRejected
BookmarkItemOrderModelTests.testMovingToSamePositionKeepsOrder
BookmarkItemOrderBridgeTests.testBridgePersistsCompleteSeparatePermutationsAndManualMode
BookmarkItemOrderBridgeTests.testIncompleteDuplicateAndForeignIdsAreRejectedWithoutMutation
BookmarkItemOrderBridgeTests.testChildCollectionCannotChangeParentItemRanks
BookmarkItemOrderBridgeTests.testManualOrderAndModeSurviveKmlSaveAndReload
BookmarkItemOrderBridgeTests.testTopEditStartsManualOrderWithDeleteAndReorderControls
BookmarkItemOrderBridgeTests.testDoneEndsItemEditingAndSearchDisablesThenRestoresEdit
BookmarkItemOrderBridgeTests.testDeleteInItemEditEndsStaleOrderAndPersistsRemainingItems
Точные source paths, границы с соседними темами и список файлов: ../../plan.json.
Полный текущий план166 XCTest и Local167 не означают, что каждый из8 срезов проверен самостоятельно.

Происхождение кода/идей
{
  "kind": "CoMaps-specific AI-assisted implementation"
}

Связанные запросы CoMaps (состояния — ../../README.txt)
https://codeberg.org/comaps/comaps/issues/4881

Исторические патчи (НЕ порядок применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/427d129d9693d48bc86bab41e5e40f577c06708b/patches/manual-item-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/427d129d9693d48bc86bab41e5e40f577c06708b/patches/ios-manual-item-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/427d129d9693d48bc86bab41e5e40f577c06708b/patches/manual-bookmark-creation.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/427d129d9693d48bc86bab41e5e40f577c06708b/patches/invalidate-default-sort.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/427d129d9693d48bc86bab41e5e40f577c06708b/patches/show-reorder-controls.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/427d129d9693d48bc86bab41e5e40f577c06708b/patches/unified-saved-item-editing.patch

Mac Lab85: Edit/Done проверены на живом окне; пользователь подтвердил физический drag и
сохранение после перезапуска. Отдельная Android-сборка не выполнялась.
