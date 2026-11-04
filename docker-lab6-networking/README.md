# Лабораторная 6. Docker Networking

Готовый учебный магазин из **трёх контейнеров**: Nginx со статической страницей, Flask API и Redis с корзиной. Локальный номер папки — 6; исходное задание — **«Лабораторная работа №2. Многоконтейнерное приложение: Магазин с корзиной»**, `Docker_Week4 laby.pdf`, стр. 15–19.

## Запуск

Нужны работающий Docker Engine, Bash и Python 3 для проверочного скрипта. На macOS запусти Docker Desktop. Выполняй команды из этой папки:

```bash
./start.sh
./check.sh
```

Открой [магазин](http://localhost:8080), а прямой backend доступен на [localhost:5000/products](http://localhost:5000/products). Если порт занят:

```bash
FRONTEND_PORT=8086 BACKEND_PORT=5056 ./start.sh
FRONTEND_PORT=8086 BACKEND_PORT=5056 ./check.sh
```

`start.sh` использует только `docker build`, `docker network` и `docker run`, **без Compose**. Повторный запуск проверяет labels, пересобирает образы и пересоздаёт только контейнеры этой работы. Общая учебная корзина при этом сбрасывается. Имена ресурсов начинаются с `devops-lab6-`; скрипты откажутся менять совпавший ресурс с чужим label.

## Архитектура

```text
Браузер → localhost:8080 → Nginx
                            └─ /api/* → backend:5000 → redis:6379
Терминал → localhost:5000 ──────────────┘
```

Контейнеры `devops-lab6-frontend`, `devops-lab6-backend` и `devops-lab6-redis` подключены к пользовательской bridge-сети `devops-lab6-network`. Network aliases — `frontend`, `backend`, `redis`. Backend использует имя `redis`, Nginx — `backend`; IP-адреса не закреплены. Автоматическое DNS-разрешение имён в user-defined bridge описано в [Docker docs](https://docs.docker.com/engine/network/drivers/bridge/).

Страница использует относительный `/api`, поэтому браузеру не нужно разрешать Docker DNS и запросы имеют тот же origin. Nginx удаляет `/api/` при proxy_pass и направляет запросы в Flask. Прямой порт backend 5000 сохранён по условию лабораторной. Redis не опубликован на хост.

## API и проверка вручную

```bash
curl http://localhost:5000/products
curl http://localhost:8080/api/cart
curl -X POST http://localhost:8080/api/cart/add/1
curl -X POST http://localhost:8080/api/cart/add/2
curl http://localhost:8080/api/cart
```

На пустой корзине товары 1 и 2 дают `count=2`, `total=40`. Цены из исходника: Docker T-Shirt — 25, Kubernetes Mug — 15, DevOps Book — 40. Добавление всех трёх даёт 80. Неизвестный ID возвращает 404 и не меняет корзину. `DELETE /cart` очищает только учебный Redis-ключ `devops:lab6:cart`.

Дополнительный `GET /health` проверяет доступность Redis. Redis-ошибка возвращает понятный JSON 503. Flask работает через Gunicorn от UID 10001. У всех трёх контейнеров есть healthcheck.

## Проверки и доказательства

`./check.sh` выполняет реальные HTTP-запросы и Docker DNS-проверку; он очищает только общую корзину данного магазина, затем создаёт контролируемый набор товаров. Результат — `evidence/checks.json`, ненулевой exit code при любой ошибке. Тест проверяет цены, суммы, HTTP 404 без мутации, прямой backend, proxy Nginx, три DNS aliases и ровно три контейнера в сети.

`tests/browser-check.cjs` — дополнительный браузерный сценарий при установленном Playwright: он нажимает кнопки, проверяет сумму $40, делает реальные desktop/mobile PNG и проверяет отсутствие горизонтального overflow и JS-ошибок. Можно указать путь модуля через `PLAYWRIGHT_MODULE`, а исполняемый браузер через `CHROMIUM_EXECUTABLE`; обычная HTTP-проверка Playwright не требует.

Другие доказательства:

- `evidence/build-start.log` — фактическая сборка и запуск;
- `evidence/environment.json` — версии Engine, image IDs, архитектура и health;
- `evidence/backend-dependencies.txt` — реальные установленные Python-пакеты;
- `evidence/container-logs.txt` — логи контейнеров;
- `REPORT.md` — результаты и соответствие условию.

## Остановка

```bash
./stop.sh
```

Удаляются только собственные три контейнера и сеть. Другие проекты и образы не затрагиваются. Redis использует `/data` в tmpfs, без AOF/snapshots: долговечность корзины здесь не обещается. Это лабораторная по сетям; постоянные PostgreSQL/Redis volumes реализованы в `docker-lab9-compose`.

## Отличия от учебного фрагмента

Сохранены все три роли, адреса по умолчанию, каталог и Redis-корзина. Добавлены proxy для корректного browser-to-API взаимодействия, обработка неизвестного товара, явные healthchecks, ожидание readiness, Gunicorn, non-root API и автоматические проверки. Flask/Python обновлены до реально проверенного стека; точные версии находятся в requirements и evidence. Публикация в registry не выполнялась.
