01-track-rename: Сохранение имени трека

AI-assisted техническая карточка для личного разбора CoMaps. Не готовый текст PR.

Проблема и результат
Переименование помечает трек изменённым, поэтому обычное автосохранение записывает имя. Это
устраняет одну локальную причину отката имени.

Границы
Не исправляет все облачные откаты. Для самостоятельного теста явно создать bookmarks directory:
совмещённый набор мог наследовать подготовку от предыдущего теста.

Готовность
Изменение входит в общий Lab. Самостоятельный patch/CI этой темы ещё не выделен.
Ни одна тема не опубликована в CoMaps.

Зависимости
Обязательных логических предпосылок нет; общие hunks всё равно нужно разделить.

Регрессии общего набора
TrackRename_AutoSave
Точные source paths, границы с соседними темами и список файлов: ../../plan.json.
Полный текущий план166 XCTest и Local167 не означают, что каждый из8 срезов проверен самостоятельно.

Происхождение кода/идей
{
  "source_commit": "65e7523dd64eecf3db1cc1ff1d7b7fae26498597",
  "source_url": "https://github.com/organicmaps/organicmaps/commit/65e7523dd64eecf3db1cc1ff1d7b7fae26498597",
  "adaptation": "One-line source change; new AI-assisted persistence regression."
}

Связанные запросы CoMaps (состояния — ../../README.txt)
https://codeberg.org/comaps/comaps/issues/4232

Исторические патчи (НЕ порядок применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/5f66a6ca934f1675f3fc2db6af77b1e36eb69499/patches/track-rename.patch
