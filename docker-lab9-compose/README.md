# Лабораторная 9. Docker Compose

Готовый API с PostgreSQL и Redis. Локальный номер проекта — 9; исходное задание — **«Лабораторная работа №5. Multi-container приложение с Docker Compose»**, `Docker_Compose.pdf`, стр. 22–29. Выбран Flask. Опциональный Nginx не добавлен: проект содержит три обязательных сервиса `api`, `db`, `redis`.

## Запуск одной командой

Нужны Docker Engine с Compose, Bash и Python 3. Из корня проекта:

```bash
./start.sh
```

Скрипт создаёт локальный `.env` с криптографически случайным паролем и mode 0600, проверяет YAML и выполняет `docker compose up --build -d --wait`. Повторный запуск **сохраняет** пароль; смена env-пароля не меняет пароль уже существующей PostgreSQL-роли.

API: [http://localhost:5059](http://localhost:5059). Другой внешний порт можно указать перед первой конфигурацией: `API_PORT=5069 ./start.sh`. Для уже созданного `.env` поменяй `API_PORT` в нём, затем повтори запуск.

`configure.sh` можно вызвать отдельно. Не копируй `.env.example` поверх готового `.env`: example показывает ключи, а генератор создаёт собственное значение. Сохрани свой `.env` приватно вместе с локальными настройками, не добавляй в Git и не включай в архив сдачи. В соответствии с выбранным устройством репозитория здесь нет `.gitignore`; добавь `docker-lab9-compose/.env` в локальный `.git/info/exclude` репозитория. Для сдачи нужен только `.env.example`, не реальный `.env`.

## Архитектура и данные

```text
localhost:5059 → api:5000 → db:5432 (PostgreSQL 15)
                         └→ redis:6379 (cache-aside, TTL 60 секунд)
```

Сеть `devops-lab9-backend` — user-defined bridge. Внутренние имена — `db` и `redis`; порты хоста для БД и Redis не публикуются. API запускается Gunicorn от UID 10001, считывает и валидирует runtime env. Пароля нет в Dockerfile, коде, example и evidence.

Данные размещены в named volumes:

| Volume | Назначение |
| --- | --- |
| `devops-lab9-postgres-data` | PostgreSQL `/var/lib/postgresql/data` |
| `devops-lab9-redis-data` | Redis `/data`, AOF включён |

`db/init.sql` создаёт таблицу users при первой инициализации пустого PostgreSQL volume. Изменение init.sql позже не является миграцией: для заполненного volume применяй SQL/миграции отдельно. [Official PostgreSQL image](https://github.com/docker-library/docs/blob/master/postgres/README.md).

У db и redis есть healthchecks, API ждёт их через длинный `depends_on: condition: service_healthy`. У API дополнительно есть HTTP healthcheck. Все три сервиса имеют `restart: unless-stopped`. Healthcheck обеспечивает начальное ожидание готовности; приложение отдельно обрабатывает дальнейший отказ БД/кеша. [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/).

## Все семь endpoints

| Endpoint | Что проверять |
| --- | --- |
| `GET /` | Информация об API и TTL |
| `GET /health` | Liveness HTTP-процесса, `scope=http-process` |
| `GET /db-test` | SQL-подключение к PostgreSQL, версия сервера |
| `GET /cache-test` | Реальный set/get Redis с TTL |
| `POST /users` | JSON name/email → PostgreSQL, HTTP 201 |
| `GET /users` | Список из PostgreSQL |
| `GET /users/<id>` | Cache-aside: Redis hit либо PostgreSQL + кеш |

```bash
curl http://localhost:5059/health
curl http://localhost:5059/db-test
curl http://localhost:5059/cache-test
curl -i -X POST http://localhost:5059/users \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alice","email":"alice@example.com"}'
curl http://localhost:5059/users
```

Используй реальный ID из POST в `GET /users/<id>`. Первая загрузка показывает `source=database`, повторная — `source=cache`; время кеша ограничено `CACHE_TTL_SECONDS`. Пароль не возвращается в HTTP. Запросы SQL параметризованы, email уникален, пустые/неправильные данные дают 400, повторный email — 409, отсутствующий пользователь — 404. Это минимальная учебная валидация, а не полная RFC-проверка email или система регистрации.

При отказе Redis чтение пользователя продолжает работать из PostgreSQL. `/cache-test` возвращает 503. При отказе БД `/db-test` и требующие SQL операции возвращают 503 без connection string в ответе. `/health` остаётся проверкой процесса; он намеренно не выдаёт liveness за readiness всех зависимостей.

## Автоматическая проверка с реальным пересозданием

```bash
./check.sh
```

Проверка запускается на **реально работающем** проекте и:

1. Проверяет все семь endpoints и HTTP 400/404/405/409.
2. Создаёт пользователя с уникальным synthetic email, проверяет DB → cache и TTL.
3. Проверяет истечение копии: задаёт TTL одного тестового ключа в 1 секунду и снова получает пользователя из БД.
4. Останавливает только `devops-lab9-redis`, проверяет 503 cache-test и успешный fallback, затем запускает Redis.
5. Останавливает только `devops-lab9-db`, проверяет различие liveness/доступности БД, затем запускает PostgreSQL.
6. Записывает Redis marker без TTL, сохраняет container IDs и mounts.
7. Выполняет **`docker compose down` без `-v`**, затем `up --wait`.
8. Доказывает новые container IDs, прежние volumes, сохранённого пользователя PostgreSQL и marker Redis AOF.

Итог записывается в `evidence/checks.json`; при ошибке exit code ненулевой. На каждом запуске остаётся один дополнительный демонстрационный пользователь и свой marker. Данные других проектов не читаются и не удаляются. Во время теста проект временно недоступен — это управляемые сценарии отказа.

`.env` не печатается: сырые inspect/env не сохраняются, а отчёт дополнительно редактирует точное значение пароля. `configuration_without_password` содержит только несекретные параметры. Лог реальной сборки находится в `evidence/build-start.log`, измерения среды — в `evidence/environment.json`.

## Остановка и повторный запуск

```bash
./stop.sh
./start.sh
```

Stop удаляет только контейнеры и сеть этого Compose-проекта; оба named volumes остаются. Старт использует прежний `.env` и прежние данные. Скрипты проверяют `devops.lab=9` у существующих одноимённых ресурсов и отказываются менять чужие.

Удаление volumes — отдельный разрушительный сброс тестовых данных, для обычной остановки он не нужен. Если после сдачи решишь полностью удалить данные именно этой работы, сначала останови проект, сохрани нужное и явно выполни `docker volume rm devops-lab9-postgres-data devops-lab9-redis-data`. Глобальный prune не требуется.

## Что сдавать

Исходник проекта с Compose/API/SQL, README, `.env.example`, `REPORT.md` и реальные evidence. Реальный `.env` из архива исключить. В исходном PDF пример app.py не содержал `/users` и схему — здесь эти обязательные части реализованы. Фактические проверки и ограничения указаны в отчёте; публикация образа в registry не выполнялась.
