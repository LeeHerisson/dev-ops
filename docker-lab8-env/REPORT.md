# Отчёт по Docker lab 8

Оригинал задания: ЛР4 «Environment Variables & Configuration», Docker_Volumes_EnvVars.pdf, страницы 23–28, исходный код на страницах 16–18. Сквозная рабочая нумерация: lab8.

Фактическая проверка: 2026-11-04T06:10:46.499057+00:00; статус **passed**, run ID `20261104-final`.
Docker Engine: `29.9.2/linux/arm64`. Оба режима запущены из одного image ID `sha256:5ff2c62fc8115f26ed740d022b9fb76dcd3c8c7c1caf5855905782c4500e047f`.

| Реальная проверка | Результат |
|---|---|
| development: HTTP и режим DEBUG | PASS |
| development: реальный PostgreSQL и нужная БД | PASS |
| development: процесс non-root | PASS |
| production: HTTP и режим DEBUG | PASS |
| production: реальный PostgreSQL и нужная БД | PASS |
| production: процесс non-root | PASS |
| Оба режима используют один и тот же image ID | PASS |
| Данные development не появились в production | PASS |
| Сети и volumes двух окружений различны | PASS |
| Пароли и SECRET_KEY сред независимы | PASS |
| Валидация контейнера: missing | PASS |
| Диагностика missing не раскрыла секреты | PASS |
| Валидация контейнера: debug | PASS |
| Диагностика debug не раскрыла секреты | PASS |
| Валидация контейнера: port-text | PASS |
| Диагностика port-text не раскрыла секреты | PASS |
| Валидация контейнера: port-range | PASS |
| Диагностика port-range не раскрыла секреты | PASS |
| Валидация контейнера: prod-debug | PASS |
| Диагностика prod-debug не раскрыла секреты | PASS |
| HTTP ответы не содержат секретов | PASS |
| Конфигурация образа не содержит реальных секретов | PASS |
| Env-файлы не скопированы в runtime image | PASS |
| Локальные секретные env-файлы имеют права 0600 | PASS |

Результаты HTTP и безопасные сведения о ресурсах: `evidence/verification.json`. Настоящие unit-тесты выполнены внутри Docker test-stage; вывод: `evidence/build-tests.txt`. Runtime собирается отдельно и не включает tests или env-файлы.

Development и production используют отдельные сети, named volumes и реальные PostgreSQL 15. В обеих сетях имя БД — `db`, а содержимое и учётные данные независимы. Пароли и SECRET_KEY сгенерированы локально и не выведены в evidence. DB-порты на хосте не публикуются.

Это учебный production-like режим конфигурации: в нём DEBUG=false, но используется development server Flask из задания. Публичного deployment и Docker Hub публикации не было. Для промышленного deployment нужны WSGI, TLS и отдельная эксплуатационная конфигурация.

По завершении выполнения контейнеры остановлены; volumes сохранены. Команда `./run.sh start` возобновляет сохранённый запуск, `./run.sh check` повторяет проверки. Очистка данных выполняется только явным `./run.sh cleanup --delete-data`.

## Дополнительная проверка защиты имён

Дата: 2026-11-04T06:29:35.671094+00:00. Новый запуск предварительно проверяет все запланированные имена контейнеров, сетей и volumes без фильтра labels, до configure/build/create. Resume проверяет owner/lab/run всех восьми сохранённых ресурсов до первого start.

В реальном regression-тесте отдельный синтетический volume получил ожидаемое имя development volume и чужие labels. CLI отказался до сборки образов и подключения данных. Содержимое, labels, исходные state/verification файлы остались неизменны; runtime и test images для тестового run ID не появились. 8/8 проверок PASS. Синтетический volume удалён; существующие volumes лабораторной не изменялись. Протокол: `evidence/collision-guard.json`.

Полный dev/prod запуск после правки preflight не повторялся: приложение и Dockerfile не менялись; результаты 12 unit-тестов и 24 основных проверок выше относятся к исходному финальному запуску.
