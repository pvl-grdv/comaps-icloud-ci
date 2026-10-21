03-save-delete-safety: Безопасное сохранение и удаление

AI-assisted техническая карточка для личного разбора CoMaps. Не готовый текст PR.

Проблема и результат
При ошибке удаления или переноса папка остаётся в памяти. Перед переносом в корзину сохраняются
последние правки; устаревшее отложенное сохранение не воскрешает удалённый файл. Ошибка открытия
файла возвращается вызывающему коду.

Границы
Нет нового механизма повторных попыток сохранения. Синхронная запись большой папки перед
корзиной может задержать UI. Есть изменения Android Java; отдельная Android-сборка пока не
подтверждена.

Готовность
Изменение входит в общий Lab. Самостоятельный patch/CI этой темы ещё не выделен.
Ни одна тема не опубликована в CoMaps.

Зависимости
02-category-reload

Регрессии общего набора
Bookmarks_DeletionFailurePreservesCategoryAndChildren
Bookmarks_TrashFailurePreservesCategory
Bookmarks_QueuedSaveDoesNotRecreateDeletedFile
Bookmarks_TrashPreservesQueuedEdits
Bookmarks_FailedDeletionKeepsQueuedSaveActive
Bookmarks_TrashPreservesUncommittedEditSession
Bookmarks_TrashPreservesMemoryAfterFailedAutosave
Точные source paths, границы с соседними темами и список файлов: ../../plan.json.
Полный текущий план166 XCTest и Local167 не означают, что каждый из8 срезов проверен самостоятельно.

Происхождение кода/идей
{
  "source_commit": "01e8b634df68750ce15b86aec19ceed4362eb24e",
  "source_url": "https://github.com/organicmaps/organicmaps/commit/01e8b634df68750ce15b86aec19ceed4362eb24e",
  "adaptation": "Narrow adaptation preserving CoMaps Java void deleteCategory wrapper; tryDeleteCategory reports boolean. Native shared save state, failure-preserving UI/bridge handling and new regressions were adapted for this candidate."
}

Исторические патчи (НЕ порядок применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/427d129d9693d48bc86bab41e5e40f577c06708b/patches/ios-folder-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/427d129d9693d48bc86bab41e5e40f577c06708b/patches/deletion-autosave-safety.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/427d129d9693d48bc86bab41e5e40f577c06708b/patches/save-open-failure.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/427d129d9693d48bc86bab41e5e40f577c06708b/patches/persist-deletion-fixture.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/427d129d9693d48bc86bab41e5e40f577c06708b/patches/incoming-bookmark-ordered-commit.patch
