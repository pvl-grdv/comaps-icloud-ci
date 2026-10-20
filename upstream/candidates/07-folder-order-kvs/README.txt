07-folder-order-kvs: Передача порядка папок через iCloud KVS

AI-assisted техническая карточка. Не готовый текст PR и не одобрение CoMaps.

Поведение
Одна системная KVS-запись передаёт режим и последовательность папок. Применение меняет bm.json без перезаписи KML. Места ещё не загруженных папок сохраняются; окончание редактирования учитывает фон и смену аккаунта.

Пределы и что проверить
Победителя целой записи выбирает системный KVS; параллельные перестановки не сливаются. Токены строятся из NFC-basename, стабильный UUID папки не введён. Тест трёх устройств использует fake stores. В Lab Local iCloud/KVS отключены.

Готовность
Реализовано и проверено только внутри общего кандидата 0237ee3737e6b2deeb80fbe03b6c72d82aee43d8.
Самостоятельная ветка/коммит/CI для этой карточки ещё не выделены.

Предпосылки: 05-manual-folder-order

Проверки в общем комплекте: core=1, search=0, XCTest=22.
Точные ID и source paths: ../../plan.json. Общие тесты описаны в verification.json;
расположение XCTest в классе не означает принадлежность всего класса одной теме.

Происхождение
{
  "kind": "CoMaps-specific AI-assisted implementation"
}

Исходные патчи (указатели, не series применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/shared-folder-order.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/folder-order-lifecycle.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/stable-category-menu-target.patch
