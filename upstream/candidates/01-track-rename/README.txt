01-track-rename: Сохранение имени трека

AI-assisted техническая карточка. Не готовый текст PR и не одобрение CoMaps.

Поведение
Переименование помечает трек изменённым, поэтому обычное автосохранение записывает имя. Это устраняет одну локальную причину отката имени.

Пределы и что проверить
Не исправляет все облачные откаты. Для самостоятельного теста явно создать bookmarks directory: совмещённый набор мог наследовать подготовку от предыдущего теста.

Готовность
Реализовано и проверено только внутри общего кандидата 0237ee3737e6b2deeb80fbe03b6c72d82aee43d8.
Самостоятельная ветка/коммит/CI для этой карточки ещё не выделены.

Предпосылки: нет обязательных логических предпосылок; общие hunks всё равно разделить

Проверки в общем комплекте: core=1, search=0, XCTest=0.
Точные ID и source paths: ../../plan.json. Общие тесты описаны в verification.json;
расположение XCTest в классе не означает принадлежность всего класса одной теме.

Происхождение
{
  "source_commit": "65e7523dd64eecf3db1cc1ff1d7b7fae26498597",
  "source_url": "https://github.com/organicmaps/organicmaps/commit/65e7523dd64eecf3db1cc1ff1d7b7fae26498597",
  "adaptation": "One-line source change; new AI-assisted persistence regression."
}

Исходные патчи (указатели, не series применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/track-rename.patch
