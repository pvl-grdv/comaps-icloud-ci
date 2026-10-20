04-saved-items-search: Поиск точек и треков

AI-assisted техническая карточка. Не готовый текст PR и не одобрение CoMaps.

Поведение
Общий поиск и поиск внутри папки находят точки и треки. Типизированный ID различает точку и трек с одинаковым числовым ID. Устаревшие ответы, отмена и удалённые результаты обрабатываются явно.

Пределы и что проверить
Описания поддерживаются ядром только при включённом флаге; iOS его не включает. Названия папок не индексируются. Для точек есть оригинальные/пользовательские имена и типовые псевдонимы; у треков используется предпочтительное локализованное имя. На большой реальной библиотеке производительность не измерена.

Готовность
Реализовано и проверено только внутри общего кандидата 0237ee3737e6b2deeb80fbe03b6c72d82aee43d8.
Самостоятельная ветка/коммит/CI для этой карточки ещё не выделены.

Предпосылки: нет обязательных логических предпосылок; общие hunks всё равно разделить

Проверки в общем комплекте: core=0, search=11, XCTest=19.
Точные ID и source paths: ../../plan.json. Общие тесты описаны в verification.json;
расположение XCTest в классе не означает принадлежность всего класса одной теме.

Происхождение
{
  "kind": "CoMaps-specific AI-assisted implementation"
}

Исходные патчи (указатели, не series применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/global-bookmark-search.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/typed-saved-items-search.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/typed-saved-items-ios.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/typed-search-cancellation.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/hosted-bookmarks-ui-smoke.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/search-viewport-test-setup.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/cancellation-test-explicit-catch.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/bookmark-original-name-search-alias.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/explicit-search-service-capture.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/hosted-ui-window-lifecycle.patch
