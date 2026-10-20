06-manual-item-order: Ручной порядок точек и треков

AI-assisted техническая карточка. Не готовый текст PR и не одобрение CoMaps.

Поведение
Внутри папки точки и треки остаются в отдельных разделах. Полный корректный порядок сохраняется в KML через comaps:itemOrder и comaps:itemSorting; добавление, перенос, удаление и undo учитывают ранги.

Пределы и что проверить
Смешанный список точек и треков не реализован. Две конфликтующие KML-версии не сливаются по отдельным рангам. JNI fallback сохраняет совместимость, но Android UI ручного порядка не добавлен. Отдельной регрессии доставки уже поставленного в очередь autosort-callback после reset в плане нет.

Готовность
Реализовано и проверено только внутри общего кандидата 0237ee3737e6b2deeb80fbe03b6c72d82aee43d8.
Самостоятельная ветка/коммит/CI для этой карточки ещё не выделены.

Предпосылки: нет обязательных логических предпосылок; общие hunks всё равно разделить

Проверки в общем комплекте: core=7, search=0, XCTest=10.
Точные ID и source paths: ../../plan.json. Общие тесты описаны в verification.json;
расположение XCTest в классе не означает принадлежность всего класса одной теме.

Происхождение
{
  "kind": "CoMaps-specific AI-assisted implementation"
}

Исходные патчи (указатели, не series применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/manual-item-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/ios-manual-item-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/manual-bookmark-creation.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/invalidate-default-sort.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/show-reorder-controls.patch

Дополнительные границы проверки
Снимки HostedBookmarksUISmokeTests показывают общий поиск и порядок папок.
Экран и жест перестановки точек/треков они не проверяют. Для этой темы есть
core/model/bridge тесты, а взаимодействие в приложении ещё нужно проверить.
Отдельная Android-сборка JNI-изменений не подтверждена.
