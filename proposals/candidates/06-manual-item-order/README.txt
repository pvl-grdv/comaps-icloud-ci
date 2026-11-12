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
в плане нет. Два свежих снимка самостоятельного XCTest показывают элементы до/после Edit;
физический жест перестановки ими не проверяется. Отдельная Android-сборка JNI-изменений не подтверждена.

Готовность
Независимый срез выделен: proposals/saved-items/item-order.patch
SHA-256: ab0edb38442a625c9410f43cc0e81df6cbf23e32dc0d369eaf466a3b508ba8dd
База: 871febfffe0ef2a970d4f6973442dd80c632da01
Проверенный CI: https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/43176499388
Точный проверенный коммит: de8b66286684b9e884bfb75babe15721a13ffaac
PASS: native=8, XCTest=13,0 ошибок/пропусков/expected failures,
unsigned Release archive. Проверены реальные методы, журналы и SHA артефактов.
Доказательство: ../../evidence/item-order-43176499388.json.
Общий отчёт: ../../evidence/saved-items-43176499388.txt.
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
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/manual-item-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/ios-manual-item-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/manual-bookmark-creation.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/invalidate-default-sort.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/show-reorder-controls.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/unified-saved-item-editing.patch

Mac Lab85: Edit/Done проверены на живом окне; пользователь подтвердил физический drag и
сохранение после перезапуска. Отдельная Android-сборка не выполнялась.

Проверяемая тестовая граница
Host ожидает настоящее viewDidAppear. Проверяются штатная editButtonItem,
её действие и состояние экрана/таблицы. UIKit показывает завершение галочкой;
буквальная английская надпись Done не требуется. Все13 методов и проверки
manualmode/удаления/поиска сохранены. Два свежих PNG до/после Edit осмотрены:
../../evidence/item-order-before-edit-43176499388.png
../../evidence/item-order-after-edit-43176499388.png
Это не универсальный аудит локализации, VoiceOver или физического жеста.
История предыдущих ошибок сохранена в ../../evidence/status.json.
