# Лабораторная 5 — оптимизация React + Express

Работающий учебный блог: frontend на React с инструментами Create React App, Express API и раздача production-сборки одним процессом Node. В папке находятся две реализации одного Docker-образа: исходная single-stage и оптимизированная multi-stage. Реальные результаты проверки сохраняются в [REPORT.md](REPORT.md) и `evidence/`.

## Нумерация и источник

В репозитории это **ЛР5**, следующая работа после уже выполненного генератора QR-кодов (ЛР4). В исходном `Docker_Week4 laby.pdf` эта же работа называется **«Лабораторная работа №1 — Оптимизация приложения с использованием всех Best Practices»**, стр. 7–10, блок недели 4. Номер внутри исходного документа не совпадает со сквозным номером репозитория.

Требования: React + Express, production build frontend в статику, multi-stage, `.dockerignore`, порядок копирования для кеширования, объединение связанных RUN, Alpine runtime, non-root, размер менее 200 MB и уменьшение минимум в пять раз. Здесь MB = 1 000 000 байт: это более строгая граница, чем 200 MiB.

CRA сохранён ради буквального соответствия заданию. Используется `react-scripts@5.0.1`; минимальная структура проекта создана вручную, без лишних файлов генератора. Это именно CRA toolchain, не Vite. CRA deprecated для новых проектов; выбор здесь учебный. [Позиция команды React](https://react.dev/blog/2025/02/14/sunsetting-create-react-app).

## Что работает

- `/` — React-блог с тремя статьями, поиском, фильтрами и чтением статьи в диалоге.
- `/api/health` — JSON `{"status":"ok","message":"Server is running"}`.
- `/api/posts` — содержимое блога; frontend получает его настоящим HTTP-запросом.
- `/posts/1` — SPA fallback на production `index.html`.
- Неизвестные API-маршруты и отсутствующие `.js`-файлы возвращают 404, а не HTML с кодом 200.
- SIGTERM корректно закрывает HTTP server. Optimized runtime работает от пользователя `node` и имеет Docker healthcheck.

В проекте нет базы, пользовательской записи и секретов. Статьи хранятся в версионируемом `server/posts.json`.

## Структура

```text
client/
  public/index.html
  src/App.js, index.js, styles.css
  package.json
  package-lock.json
server/
  server.js, app.js, posts.json
  tests/app.test.js
  package.json
  package-lock.json
scripts/verify.mjs
Dockerfile
Dockerfile.baseline
.dockerignore
README.md
REPORT.md
evidence/
```

Express закреплён на совместимом major 4: wildcard `app.get('*')` в Express 5 имеет другой синтаксис. Оба дерева зависимостей фиксируются lock-файлами и устанавливаются через `npm ci`. Базовые теги `node:24` и `node:24-alpine` могут обновляться; точные использованные image IDs и фактическая версия Node записаны в evidence. [Изменения Express 5](https://expressjs.com/en/guide/migrating-5/#path-syntax).

## Воспроизвести всю Docker-проверку

Нужны работающий Docker Engine / Docker Desktop, CLI, Node 24 на хосте и доступ к Docker Hub/npm registry для скачивания публичных зависимостей. Авторизация и публикация образов не требуются.

Из каталога этой работы:

```bash
node scripts/verify.mjs
```

Скрипт собирает оба образа под `linux/arm64`, измеряет `.Size` в байтах, проверяет обе HTTP-реализации и статику, non-root оптимизированного варианта, Docker healthcheck, корректную остановку и повторную сборку из кеша. Он записывает команды, коды завершения и результаты в `evidence/`. Контейнеры используют динамически выданные порты loopback и удаляются в `finally`, включая случай ошибки. Удаление чужих ресурсов и `prune` не выполняются. Образы сохраняются для просмотра и повторного запуска.

На x86-машине можно выбрать нативную платформу явно, но это будет **другой** набор измерений:

```bash
LAB5_PLATFORM=linux/amd64 node scripts/verify.mjs
```

Не смешивай размеры разных платформ в одной таблице.

## Обычная сборка и запуск

```bash
docker build --platform linux/arm64 -f Dockerfile.baseline \
  -t devops-lab5-baseline:local .
docker build --platform linux/arm64 \
  -t devops-lab5-optimized:local .
docker run -d --rm --name devops-lab5-blog \
  -p 127.0.0.1:5305:3000 devops-lab5-optimized:local
curl -fsS http://localhost:5305/api/health
docker exec devops-lab5-blog id
```

Открой [блог на localhost:5305](http://localhost:5305). После демонстрации:

```bash
docker stop devops-lab5-blog
```

Флаг `--rm` удалит этот контейнер после остановки. Порт приложения внутри — 3000; host port 5305 выбран, чтобы не конфликтовать с другими лабораторными.

## Почему baseline больше

`Dockerfile.baseline` — рабочий single-stage вариант на полном `node:24`. Он оставляет Debian userland и инструменты полного Node-образа, frontend toolchain `react-scripts`, все frontend-зависимости, исходники, npm cache и готовую статику. В нём нет специально созданных файлов-заполнителей или бессмысленно добавленных гигабайтов. Он использует тот же `.dockerignore` и обслуживает те же API и статические assets.

В `Dockerfile` frontend собирается отдельно. Стадия `production-deps` на `node:24-alpine` устанавливает только серверные зависимости. Финальная стадия начинается с Alpine 3.24, соответствующего дистрибутиву проверенного Node Alpine source, и получает официальный Node 24 musl binary, его runtime-библиотеки, серверные `node_modules`, код Express и готовый `client/build`. Frontend toolchain, npm, Yarn и Node headers в финальную стадию не переносятся. Установка Alpine runtime-библиотек и создание пользователя объединены в одном RUN. В пустой Alpine-среде создаётся пользователь `node` с UID 1000, затем `USER node` переключает сервер на него. [Практики official Node image](https://github.com/nodejs/docker-node/blob/main/docs/BestPractices.md).

Такой дополнительный отбор файлов понадобился после реального первого измерения: сам текущий `node:24-alpine` превышал 200 десятичных MB по `.Size` в используемом image store. Первоначальный двухстадийный результат и ошибка критерия сохранены в `evidence/attempt-1/`. Один только отбор файлов дал 201.94 MB — эта вторая попытка сохранена в `evidence/attempt-2/`. В промежуточной стадии `strip --strip-unneeded` удаляет ненужные ELF-символы из официального Node binary, сохраняя нужные динамические символы. Binutils остаётся за пределами runtime. Итог 178.78 MB прошёл реальные HTTP и HTTPS проверки. Baseline не раздувался для сравнения; оптимизация удаляет конкретные ненужные runtime-компоненты.

Копируются **статические** frontend-файлы из Debian build stage, а не native `node_modules` между разными libc. Серверные зависимости устанавливаются в Alpine-стадии с той же libc, что у финальной среды. Нужные `libstdc++` и `libgcc` предоставляют Alpine packages; CA-сертификаты также включены. Node-бинарник не собирается из неизвестного источника: он взят из official `node:24-alpine`.

## Кеширование

В optimized Dockerfile сначала копируются `package.json` и `package-lock.json`, затем выполняется `npm ci`, потом копируются исходники. Изменение текста статьи или React-компонента не требует переустановки неизменённых зависимостей.

Повторная сборка без изменений проверяется `scripts/verify.mjs`; фактический лог находится в `evidence/optimized-cached-build.txt`. Скрипт также временно добавляет один JavaScript-комментарий, проверяет переиспользование слоя frontend `npm ci`, восстанавливает исходник и удаляет только созданный им cache-check tag. Этот результат находится в `evidence/optimized-source-change-build.txt` и `evidence/source-change-cache-check.json`. Для отдельного ручного эксперимента:

```bash
# Измени только текст в client/src/App.js.
docker build --progress=plain -t devops-lab5-optimized:local .
```

Ищи `CACHED` у `RUN npm ci` и новый шаг React build. Изменение lock-файла закономерно инвалидирует соответствующую установку. Не сравнивай сетевое скачивание первого build с чистой скоростью повторной сборки без пояснения.

## Серверные тесты без Docker

```bash
npm ci --prefix server --no-audit --no-fund
npm --prefix server test
```

Шесть тестов проверяют HTTP-контракты health/posts, unknown API 404, SPA fallback, JavaScript content type и отсутствие маскировки пропавшего asset через HTML. Они не заменяют Docker-проверку: отдельный verification запускает настоящие образы и production React assets.

## Разработка локально

```bash
npm ci --prefix client --no-audit --no-fund
npm ci --prefix server --no-audit --no-fund
```

В первом терминале:

```bash
PORT=3001 npm --prefix server start
```

Во втором:

```bash
npm --prefix client start
```

CRA dev server открывается на 3000 и проксирует `/api` к Express на 3001. Для локального production-варианта:

```bash
npm --prefix client run build
node -e "require('node:fs').cpSync('client/build','server/build',{recursive:true})"
npm --prefix server start
```

## Локальные исключения Git

По принятому для репозитория правилу `.gitignore` здесь не создаётся. В корневой `.git/info/exclude` репозитория добавь:

```gitignore
**/node_modules/
**/client/build/
**/server/build/
**/npm-debug.log*
**/.DS_Store
```

`.dockerignore` решает другую задачу: исключает эти файлы из Docker build context и не зависит от правил Git. Исходники, оба lock-файла, Dockerfile, README, REPORT и evidence должны оставаться доступными для проверки.

## Как читать результаты

Поле `.Size` — размер образа по `docker image inspect`, не размер сжатой загрузки из registry и не уникально занятое место общих слоёв. Формула: `baselineBytes / optimizedBytes`. Порог: `optimizedBytes < 200000000`, коэффициент `>= 5`. Истинные числа, проверки и возникшие ошибки записаны в REPORT; команды скрипта дополнительно перечислены в `evidence/commands.json`.

Публичная публикация Docker Hub не является частью этой реализации. Ключи и персональные данные для работы не нужны.
