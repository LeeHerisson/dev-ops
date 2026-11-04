# Лабораторная 10 — GitHub Actions и Docker

[![Docker Lab 10 CI](https://github.com/LeeHerisson/dev-ops/actions/workflows/docker-lab10.yml/badge.svg)](https://github.com/LeeHerisson/dev-ops/actions/workflows/docker-lab10.yml)

Работа по материалу «Лабораторная работа 3 — CI/CD с GitHub Actions», неделя 6. Здесь используется сквозной номер 10 для оставшихся работ после QR. Исходные номера повторяются в разных документах.

Реализован Flask ToDo API, автоматические тесты и многостадийный Dockerfile. Публикация в Docker Hub исключена по вашему уточнению от 4 ноября 2026 года: workflow проверяет код и собирает образ без отправки в registry. Токены Docker Hub не нужны.

## Быстрый запуск

```bash
cd docker-lab10-cicd
docker build -t devops-lab10-todo:local .
docker run -d --rm --name devops-lab10-todo \
  -p 127.0.0.1:5060:5000 devops-lab10-todo:local
curl -fsS http://localhost:5060/health
curl -fsS -X POST http://localhost:5060/todos \
  -H 'Content-Type: application/json' -d '{"title":"Изучить CI"}'
curl -fsS http://localhost:5060/todos
docker stop devops-lab10-todo
```

Список задач находится в памяти процесса и очищается при его завершении. Это учебная модель исходного задания; PostgreSQL и volumes изучаются в отдельных работах. Сервер Flask используется для локальной демонстрации, без публичного deployment.

## Локальные тесты

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -v
```

Четыре базовых теста сохранены в `tests/test_main.py`. Ещё шесть проверяют последовательность ID, удаление пробелов и некорректные типы/длину ввода. Итого 10 тестов.

Для воспроизведения красного теста в своей отдельной ветке замени ответ `/health` с `ok` на `OK`, запусти `test_health`, затем верни `ok`. Реальный локальный лог такого эксперимента сохранён в `evidence/intentional-failure.log`. Это локальный pytest-эксперимент; он не выдаётся за запуск GitHub Actions.

## Проверка Docker целиком

```bash
bash scripts/check.sh
```

Скрипт явно собирает stage `test` и выполняет pytest внутри него, затем собирает runtime, проверяет непривилегированный UID и отсутствие pytest. После этого запускает временный контейнер с автоматически выбранным свободным портом и проверяет реальные HTTP-запросы. Контейнер удаляется через trap даже при неуспешной проверке. Чужие контейнеры и тома скрипт не затрагивает.

Независимая test-stage не выполняется автоматически при сборке runtime: команда `docker build --target test` нужна отдельно. Runtime устанавливает только зависимости из `requirements.txt`. Образ `Dockerfile.baseline` включает pytest для измеряемого сравнения.

## Workflow в монорепозитории

Файл расположен **в корне репозитория**: `.github/workflows/docker-lab10.yml`. Вложенная `.github` внутри папки лабораторной не используется.

| Событие | Test | Build image |
|---|---|---|
| Push кода лабораторной в main | Матрица Python 3.11/3.12/3.13 | После успешных тестов |
| PR в main | Матрица | Пропуск |
| Ручной запуск из main | Матрица | После успешных тестов |
| Push, меняющий только README | Нет запуска workflow | Нет |

Ключ `needs: test` запрещает сборку после провала тестов. `if` исключает PR и другие ref. Каждая job получает собственный checkout. `defaults.run.working-directory` учитывает папку приложения в этом монорепозитории; build context не включает другие лабораторные.

`permissions: contents: read` задаёт минимальные права автоматического GitHub-токена. Пароли и сторонние токены в workflow не используются. Secrets нельзя вставлять в `run`, Dockerfile или отчёт.

Проверенные расширения из бонусов: matrix трёх Python, фильтр README-only, локальные теги по SHA/run_number, отдельная test-stage без pytest в runtime, badge. Локальный тег не означает публикацию в Docker Hub. Размеры и фактические границы проверки находятся в [REPORT.md](REPORT.md).

## Артефакты

- `Dockerfile`, `Dockerfile.baseline` — сравниваемые образы.
- `app/`, `tests/`, `requirements*.txt`, `pytest.ini` — API и тесты.
- `scripts/check.sh`, `scripts/http_check.py` — воспроизводимая проверка.
- `evidence/` — реальные логи сборок, тестов, HTTP и измерений.
- [Отчёт](REPORT.md) — результаты и ответы защиты.

Локальные `.venv/`, Python caches и env-файлы исключаются через существующие правила `.git/info/exclude` этого репозитория. `.dockerignore` отдельно ограничивает контекст сборки.

Официальные справочники: [синтаксис Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [Docker multi-stage](https://docs.docker.com/build/building/multi-stage/).
