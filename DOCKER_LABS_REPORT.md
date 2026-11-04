---
tags: [docker, labs, report]
updated: 2026-11-04
---

# Выполненные лабораторные Docker

Рабочий репозиторий: `/Users/herisson/Desktop/DevOps`. QR-генератор уже выполнен владельцем и исключён из этой работы. Подготовлены шесть следующих проектов. Сквозные номера 5–10 служат навигацией; оригинальные номера преподавателя сохранены в README каждого проекта.

Публикация Docker Hub исключена по уточнению владельца от 4 ноября 2026 года. CI выполняет тесты и сборку без отправки образа в registry.

## Проекты и результаты

| Проект | Исходное задание | Что реализовано и проверено |
|---|---|---|
| [5 — React и Express](docker-lab5-optimization/README.md) | Week4, ЛР1 | React production build, Express, multi-stage, Alpine/non-root, реальное сравнение baseline/runtime, API и статика, кеш |
| [6 — Магазин и сеть](docker-lab6-networking/README.md) | Week4, ЛР2 | Nginx/Flask/Redis через docker run; 15 HTTP/DNS-проверок и 3 браузерные проверки; корзина 25+15=40 |
| [7 — PostgreSQL и volumes](docker-lab7-volumes/README.md) | Volumes/EnvVars, ЛР3 | 8 проверок: 4 студента, 3 курса, новый container ID и прежние данные, SQL и физический backup/restore с полным сравнением |
| [8 — Env dev/prod](docker-lab8-env/README.md) | Volumes/EnvVars, ЛР4 | 12 unit-тестов и 24 runtime-проверки; два режима одного образа, разные БД, валидация env, случайные локальные секреты, корректная остановка |
| [9 — Docker Compose](docker-lab9-compose/README.md) | Compose, ЛР5 | 31 проверка: все 7 маршрутов, SQL, cache-aside/TTL, ошибки ввода, отказ Redis/БД и сохранность обоих volumes после down/up |
| [10 — CI и Docker](docker-lab10-cicd/README.md) | CI/CD, ЛР3 недели 6 | 10 API-тестов, отдельные test/runtime stages, non-root/без pytest, HTTP smoke и graceful shutdown; реальный красный и исправленный зелёный PR-запуски |

Подробные [отчёты](docker-lab5-optimization/REPORT.md) лежат в `REPORT.md` каждого проекта. `evidence/` содержит фактические логи, IDs, результаты и screenshots. Размеры образов измеряются полем Docker `.Size` в байтах на одной платформе `linux/arm64`.

Оптимизация React/Express: baseline **2 162 108 054 байт**, runtime **178 782 076 байт** — **178,78 десятичных MB** и уменьшение **в 12,09 раза**. Обе обязательные границы `< 200 MB` и `>= 5×` пройдены. Runtime сохраняет официальный Node 24 musl-бинарник в чистом Alpine, исключает npm/Yarn/build headers; ненужные ELF-символы удаляются в промежуточной стадии. Работоспособность Node, динамических библиотек, HTTPS, API и статики проверена после оптимизации.

## Запуск

Из корня репозитория переходи в папку выбранной лабораторной:

| Проект | Основная команда | Завершение |
|---|---|---|
| React/Express | `docker build -t devops-lab5-optimized:local .`, затем команда run из README | Остановить свой контейнер |
| Магазин | `bash start.sh`, затем `bash check.sh` | `bash stop.sh` |
| PostgreSQL | `bash commands.sh` | Проверка сама останавливает свои БД; cleanup отдельно |
| Dev/prod | `bash run.sh start`, затем `bash run.sh check` | `bash run.sh stop` |
| Compose | `bash start.sh`, затем `bash check.sh` | `bash stop.sh` |
| CI ToDo | `bash scripts/check.sh` | Проверка сама удаляет временный контейнер |

Фиксированные web-порты: магазин 8080/5000, Compose API 5059. Скрипт проверки ToDo и dev/prod могут выбирать свободные порты автоматически. У React-блога порт передаётся в `docker run`; пример приведён в его README.

## Конфигурация и данные

В рабочем репозитории сохранены локальные env-файлы, соответствующие уже инициализированным PostgreSQL volumes. Они имеют режим 0600 и исключены из Git через `.git/info/exclude`. В исходниках и текстовых evidence реальные сгенерированные значения паролей/ключей не обнаружены.

Для новой машины используй configure-скрипты. Не заменяй пароль в env при сохранённом кластере в ожидании автоматической смены SQL-роли: инициализационные переменные применяются к пустой БД. Named volumes сохранены для последующей проверки; удаление данных вынесено в явные cleanup-опции.

Локальный `.git/info/exclude` не передаётся через clone. В новом Git-клоне перед созданием конфигурации добавь туда правила `.env`, `.env.*`, `!.env.example`, `**/.local/`, `**/node_modules/`, `__pycache__/` и `.venv/`. На данном компьютере эти исключения уже настроены и проверены через `git check-ignore`.

SQL backup находится в `docker-lab7-volumes/evidence/backup.sql`. Дополнительная локальная копия проверенного физического архива — `docker-lab7-volumes/.local/backups/20261104-actual/postgres-volume-backup.tar.gz`; она не коммитится. Его SHA-256 и результаты восстановления указаны в отчёте lab7.

## GitHub Actions

Рабочий PR: [LeeHerisson/dev-ops#5](https://github.com/LeeHerisson/dev-ops/pull/5).

- [Намеренно падающий запуск](https://github.com/LeeHerisson/dev-ops/actions/runs/41783945392): `test_health` обнаружил `OK` вместо `ok` на трёх версиях Python.
- [Исправленный PR-запуск](https://github.com/LeeHerisson/dev-ops/actions/runs/41784111437): тесты Python 3.11/3.12/3.13 успешны, сборка skipped согласно условию PR.

Результат сборки основной ветки добавляется после интеграции окончательных проектов. Workflow находится в корневой `.github/workflows/docker-lab10.yml`, рядом с существующим CI второй DevOps-работы.

## Проверка сохранения предыдущих работ

Перед добавлением новых папок сохранён снимок хешей существовавших файлов и Git status. Прежние калькулятор, QR и пользовательские удаления старых screenshots не включаются в новые коммиты. Корневой README расширяется индексом новых лабораторных.
