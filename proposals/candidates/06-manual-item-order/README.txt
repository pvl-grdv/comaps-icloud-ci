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
SHA-256: b339dfa9daa34dca49724a4caf13ebd9d0508e311b9ff0f0a88f52a27496d9a5
База: a64450d0c7cd7cdfc792c9fc6c2dd620156abecd
Предыдущий CI: https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/39581652809 (ошибка; не успешная проверка).
Новый запуск исправленной версии требуется; ссылка появится в ../../evidence/status.json.
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
https://github.com/pvl-grdv/comaps-icloud-ci/blob/5f66a6ca934f1675f3fc2db6af77b1e36eb69499/patches/manual-item-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/5f66a6ca934f1675f3fc2db6af77b1e36eb69499/patches/ios-manual-item-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/5f66a6ca934f1675f3fc2db6af77b1e36eb69499/patches/manual-bookmark-creation.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/5f66a6ca934f1675f3fc2db6af77b1e36eb69499/patches/invalidate-default-sort.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/5f66a6ca934f1675f3fc2db6af77b1e36eb69499/patches/show-reorder-controls.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/5f66a6ca934f1675f3fc2db6af77b1e36eb69499/patches/unified-saved-item-editing.patch

Mac Lab85: Edit/Done проверены на живом окне; пользователь подтвердил физический drag и
сохранение после перезапуска. Отдельная Android-сборка не выполнялась.

Исправления тестовой границы после падения предыдущего CI
Host ожидает настоящее viewDidAppear, затем проверяет видимые public UIButton/
UILabel и семантику accessibility системной кнопки (Done может быть значком).
Отсутствующая сохранённая сортировка проверяется через hasLastSortingType;
undefined enum не читается. После Edit ручной режим остаётся обязательным.
Перед удалением фикстуры сохраняются строки/ожидаемые имена, а не читается
удалённый native-backed wrapper. Число13 и проверки поведения не уменьшены.
