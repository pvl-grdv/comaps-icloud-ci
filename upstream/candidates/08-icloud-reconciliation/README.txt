08-icloud-reconciliation: Согласование содержимого iCloud

AI-assisted техническая карточка. Не готовый текст PR и не одобрение CoMaps.

Поведение
Целостные снимки папок, SHA-256 содержимого и последняя общая версия заменяют решения по одним датам. Односторонняя правка переносится без копии, разные правки сохраняются обе. Удаления подтверждаются повторным наблюдением и проверкой перед действием. Входящий снимок устанавливается после старых сохранений с защитой новых правок в памяти; общую версию подтверждает только реальная успешная запись.

Пределы и что проверить
Нет очистки старых дублей, семантического KML-dedup или стабильного UUID. Разные байты без общей базы могут сохраняться как конфликт. Уже принятая операция может завершиться после stop/account switch; устаревший результат не подтверждает новую базу. Правка после preflight может допустить старую принятую выгрузку, защищая более новую память. Настоящие 3 устройства и OS NSFileVersion-конфликт не проверены.

Готовность
Реализовано и проверено только внутри общего кандидата 0237ee3737e6b2deeb80fbe03b6c72d82aee43d8.
Самостоятельная ветка/коммит/CI для этой карточки ещё не выделены.

Предпосылки: 02-category-reload, 03-save-delete-safety

Проверки в общем комплекте: core=28, search=0, XCTest=102.
Точные ID и source paths: ../../plan.json. Общие тесты описаны в verification.json;
расположение XCTest в классе не означает принадлежность всего класса одной теме.

Происхождение
{
  "upstream_pr": "https://github.com/organicmaps/organicmaps/pull/13232",
  "upstream_head": "5f24813d6fd93f26cb216d823ab4d5996d49d192",
  "main_commit": "2b6740f79b07ad7fba24e5c99c81420d69369f64",
  "deletion_prerequisite": "01e8b634df68750ce15b86aec19ceed4362eb24e",
  "source_manifest": "patches/om13232-source-manifest.json",
  "test_mapping": "patches/om13232-coverage-map.json",
  "adaptation": "Main reconciliation and prerequisites, not unrelated CarPlay/Android UI/OM project replacement. Final CoMaps native boundary, saved-revision guards, opaque account equality, monitor lifecycle correction and per-operation coordinator ownership include candidate-specific AI-assisted adaptations."
}

Исходные патчи (указатели, не series применения)
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/initial-conflict.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/incoming-bookmark-ordered-commit.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/incoming-category-staging.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/explicit-fixture-callbacks.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/parser-rejected-invalid-snapshot-fixture.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/declare-fill-empty-names.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/icloud-content-reconciliation.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/fingerprint-tests-coordination-budget.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/per-operation-coordinators.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/writer-tests-file-worker-adapter.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/fingerprint-tests-functional-io-deadline.patch
https://github.com/pvl-grdv/comaps-icloud-ci/blob/0237ee3737e6b2deeb80fbe03b6c72d82aee43d8/patches/store-tests-functional-io-deadline.patch

Границы выделения
Финальный SynchronizaionManager напрямую вызывает
BookmarkFolderOrderSynchronization.shared.start(). Если выделять 08 без 07,
нужно убрать/адаптировать этот вызов, связанные поля и wiring тестовых mock.
Копирование финального manager целиком требует 07, хотя алгоритм согласования
содержимого логически независим от передачи порядка.
initial-conflict.patch — заменённый промежуточный эксперимент, не девятый PR.
