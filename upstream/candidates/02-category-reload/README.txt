02-category-reload: Перезагрузка метаданных папки

AI-assisted техническая карточка. Не готовый текст PR и не одобрение CoMaps.

Поведение
Загрузка обновляет существующую папку с сохранением локального ID, заменяет метаданные и старые дочерние коллекции. Проверка уникальности имени исключает саму папку; экран информации обновляется.

Пределы и что проверить
Не объединяет уже существующие одинаковые файлы. Поздний compile-fix включить в итоговые hunks, не брать весь presenter с несвязанным поиском и сортировкой.

Готовность
Реализовано и проверено только внутри общего кандидата 0237ee3737e6b2deeb80fbe03b6c72d82aee43d8.
Самостоятельная ветка/коммит/CI для этой карточки ещё не выделены.

Предпосылки: нет обязательных логических предпосылок; общие hunks всё равно разделить

Проверки в общем комплекте: core=2, search=0, XCTest=0.
Точные ID и source paths: ../../plan.json. Общие тесты описаны в verification.json;
расположение XCTest в классе не означает принадлежность всего класса одной теме.

Происхождение
{
  "upstream_pr": "https://github.com/organicmaps/organicmaps/pull/13679",
  "upstream_merge": "3916dc98db02a70ec9fb83931df5d007bd5746a7",
  "upstream_commits": [
    "a16f6fb50e03693b3aef29c695d1e044640ac0a2",
    "b4226eb5aa9b603adac6b8a674c493922c8b7bd9",
    "82b5b5c9c7939d236eb651c210bea643d0f625a0"
  ]
}

Исходные патчи (указатели, не series применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/category-reload.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/category-info-compile-fix.patch
