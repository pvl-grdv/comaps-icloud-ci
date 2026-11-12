05-manual-folder-order: Ручной порядок папок

AI-assisted техническая карточка для личного разбора CoMaps. Не готовый текст PR.

Проблема и результат
iOS показывает существующие режимы ядра: дата, имя, ручной порядок. Ручная перестановка
сохраняется в bm.json; новые пустые папки сначала получают сохранённый файл. Меню удерживает ID
папки при перестановке списка.

Границы
Автотесты переставляют datasource и осматривают UIKit; физический drag ими не
проверяется. Пользователь подтвердил drag и сохранение после перезапуска Mac Lab.
В самостоятельном срезе нет облачных или incoming-bridge изменений; KVS относится к теме07.

Готовность
Независимый срез выделен: proposals/saved-items/folder-order.patch
SHA-256: 6fd4191c2d0fe4a3b47be123c8ae081019ecf7314de4e7065deec428761e3727
База: 871febfffe0ef2a970d4f6973442dd80c632da01
Проверенный CI: https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/43176499388
Точный проверенный коммит: de8b66286684b9e884bfb75babe15721a13ffaac
PASS: native=3, XCTest=9,0 ошибок/пропусков/expected failures,
unsigned Release archive. Проверены реальные методы, журналы и SHA артефактов.
Доказательство: ../../evidence/folder-order-43176499388.json.
Общий отчёт: ../../evidence/saved-items-43176499388.txt.
Ни одна тема не опубликована в CoMaps.

Зависимости
Обязательных логических предпосылок нет; общие hunks всё равно нужно разделить.

Регрессии общего набора
Bookmarks_ManualFolderOrderPersistsEmptyCategories
Bookmarks_NewCategorySaveFailureRestoresUnsavedState
BookmarkFolderOrderTests.testManualOrderMovesNewEmptyCategories
BookmarkFolderOrderTests.testAutomaticModeRejectsMoves
BookmarkFolderOrderTests.testInvalidDestinationsLeaveOrderUntouched
BookmarkFolderOrderTests.testUnknownCategoryLeavesOrderUntouched
BookmarkFolderOrderTests.testNewFolderIsAppendedToExistingManualOrder
BookmarkFolderOrderTests.testAutomaticSortRestoresCategoryNameOrder
BookmarkFolderOrderTests.testSynchronizationEndedNotificationClosesFolderEditingUI
BookmarkFolderOrderTests.testMenuTargetRemainsSameCategoryAfterRemoteOrderChanges
BookmarkFolderOrderTests.testRemovedMenuTargetNoLongerResolvesToAnotherCategory
HostedBookmarksUISmokeTests.testHostedLibraryOrderingAndSearchScreens
Точные source paths, границы с соседними темами и список файлов: ../../plan.json.
Полный текущий план166 XCTest и Local167 не означают, что каждый из8 срезов проверен самостоятельно.

Происхождение кода/идей
{
  "kind": "existing CoMaps core exposed and extended on iOS"
}

Связанные запросы CoMaps (состояния — ../../README.txt)
https://codeberg.org/comaps/comaps/pulls/4377
https://codeberg.org/comaps/comaps/issues/4881

Исторические патчи (НЕ порядок применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/ios-folder-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/hosted-bookmarks-ui-smoke.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/show-reorder-controls.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/folder-order-lifecycle.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/stable-category-menu-target.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/2d3c2da80f1e4c3a850d8820c68311952744bbe4/patches/hosted-ui-window-lifecycle.patch

У общего набора10 XCTest этого класса; один входящий/cloud тест принадлежит теме08. В
самостоятельном folder-order остаётся9. KVS не входит в этот patch.

Исторический CI39580010991 был успешным на базе a644; он сохранён как история
и не подменяет новую независимую проверку CI43176499388 на базе871febff.
