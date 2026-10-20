03-save-delete-safety: Безопасное сохранение и удаление

AI-assisted техническая карточка. Не готовый текст PR и не одобрение CoMaps.

Поведение
При ошибке удаления или переноса папка остаётся в памяти. Перед переносом в корзину сохраняются последние правки; устаревшее отложенное сохранение не воскрешает удалённый файл. Ошибка открытия файла возвращается вызывающему коду.

Пределы и что проверить
Нет нового механизма повторных попыток сохранения. Синхронная запись большой папки перед корзиной может задержать UI. Есть изменения Android Java; отдельная Android-сборка пока не подтверждена.

Готовность
Реализовано и проверено только внутри общего кандидата 0237ee3737e6b2deeb80fbe03b6c72d82aee43d8.
Самостоятельная ветка/коммит/CI для этой карточки ещё не выделены.

Предпосылки: 02-category-reload

Проверки в общем комплекте: core=7, search=0, XCTest=0.
Точные ID и source paths: ../../plan.json. Общие тесты описаны в verification.json;
расположение XCTest в классе не означает принадлежность всего класса одной теме.

Происхождение
{
  "source_commit": "01e8b634df68750ce15b86aec19ceed4362eb24e",
  "source_url": "https://github.com/organicmaps/organicmaps/commit/01e8b634df68750ce15b86aec19ceed4362eb24e",
  "adaptation": "Narrow adaptation preserving CoMaps Java void deleteCategory wrapper; tryDeleteCategory reports boolean. Native shared save state, failure-preserving UI/bridge handling and new regressions were adapted for this candidate."
}

Исходные патчи (указатели, не series применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/ios-folder-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/deletion-autosave-safety.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/save-open-failure.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/persist-deletion-fixture.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/incoming-bookmark-ordered-commit.patch

Границы выделения
Регрессия Bookmarks_NewCategorySaveFailureRestoresUnsavedState учитывается один
раз в 05. При выделении rollback первого сохранения без ручного порядка её
нужно перенести/разделить для 03. Для helper, обрабатывающего ошибку открытия,
также требуется узкая регрессия в самостоятельном срезе.
