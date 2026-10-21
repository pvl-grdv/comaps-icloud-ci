02-category-reload: Перезагрузка метаданных папки

AI-assisted техническая карточка для личного разбора CoMaps. Не готовый текст PR.

Проблема и результат
Загрузка обновляет существующую папку с сохранением локального ID, заменяет метаданные и старые
дочерние коллекции. Проверка уникальности имени исключает саму папку; экран информации
обновляется.

Границы
Не объединяет уже существующие одинаковые файлы. Поздний compile-fix включить в итоговые hunks,
не брать весь presenter с несвязанным поиском и сортировкой.

Готовность
Изменение входит в общий Lab. Самостоятельный patch/CI этой темы ещё не выделен.
Ни одна тема не опубликована в CoMaps.

Зависимости
Обязательных логических предпосылок нет; общие hunks всё равно нужно разделить.

Регрессии общего набора
Bookmarks_ReloadPreservesCategoryIdentityAndMetadata
Bookmarks_ReloadReplacesCompilations
Точные source paths, границы с соседними темами и список файлов: ../../plan.json.
Полный текущий план166 XCTest и Local167 не означают, что каждый из8 срезов проверен самостоятельно.

Происхождение кода/идей
{
  "upstream_pr": "https://github.com/organicmaps/organicmaps/pull/13679",
  "upstream_merge": "3916dc98db02a70ec9fb83931df5d007bd5746a7",
  "upstream_commits": [
    "a16f6fb50e03693b3aef29c695d1e044640ac0a2",
    "b4226eb5aa9b603adac6b8a674c493922c8b7bd9",
    "82b5b5c9c7939d236eb651c210bea643d0f625a0"
  ]
}

Исторические патчи (НЕ порядок применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/5f66a6ca934f1675f3fc2db6af77b1e36eb69499/patches/category-reload.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/5f66a6ca934f1675f3fc2db6af77b1e36eb69499/patches/category-info-compile-fix.patch
