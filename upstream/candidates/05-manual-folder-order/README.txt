05-manual-folder-order: Ручной порядок папок

AI-assisted техническая карточка. Не готовый текст PR и не одобрение CoMaps.

Поведение
iOS показывает существующие режимы ядра: дата, имя, ручной порядок. Ручная перестановка сохраняется в bm.json; новые пустые папки сначала получают сохранённый файл. Меню удерживает ID папки при перестановке списка.

Пределы и что проверить
Тесты переставляют datasource и осматривают UIKit; физический drag не проверен. Часть финального controller/model содержит облачные и incoming-bridge hunks: выделять по поведению.

Готовность
Реализовано и проверено только внутри общего кандидата 0237ee3737e6b2deeb80fbe03b6c72d82aee43d8.
Самостоятельная ветка/коммит/CI для этой карточки ещё не выделены.

Предпосылки: нет обязательных логических предпосылок; общие hunks всё равно разделить

Проверки в общем комплекте: core=2, search=0, XCTest=10.
Точные ID и source paths: ../../plan.json. Общие тесты описаны в verification.json;
расположение XCTest в классе не означает принадлежность всего класса одной теме.

Происхождение
{
  "kind": "existing CoMaps core exposed and extended on iOS"
}

Исходные патчи (указатели, не series применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/ios-folder-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/hosted-bookmarks-ui-smoke.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/show-reorder-controls.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/folder-order-lifecycle.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/stable-category-menu-target.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/hosted-ui-window-lifecycle.patch
