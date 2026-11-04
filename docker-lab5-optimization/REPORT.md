# Отчёт по ЛР5 — оптимизация React и Express

Проверка выполнена **4 ноября 2026 года** на Docker Desktop: Docker Engine **29.9.2**, Linux **aarch64**, целевая платформа обоих образов **linux/arm64**. Node в финальном контейнере: **v24.22.2**. Хостовый Node для проверочного скрипта: v24.18.0.

Сквозная нумерация репозитория: **ЛР5**, после QR-генератора ЛР4. Источник: `Docker_Week4 laby.pdf`, **лабораторная №1 продвинутого блока недели 4**, стр. 7–10.

## Результат

| Вариант | `.Size`, байты | Десятичные MB | Платформа |
| --- | ---: | ---: | --- |
| Рабочий baseline `devops-lab5-baseline:local` | 2 162 108 054 | 2162.11 | linux/arm64 |
| Итоговый `devops-lab5-optimized:local` | 178 782 076 | 178.78 | linux/arm64 |

Коэффициент: **2 162 108 054 / 178 782 076 = 12.09×**. Выполнены оба числовых критерия: **178 782 076 < 200 000 000** и **12.09 ≥ 5**.

Измеряется поле `.Size` из `docker image inspect`. Это не размер сжатого push и не сумма уникально занятого места на диске со всеми общими слоями. Полные исходные данные: [sizes.json](evidence/sizes.json), [baseline image inspect](evidence/baseline-image-inspect.json.txt), [optimized image inspect](evidence/optimized-image-inspect.json.txt). Идентификаторы в этих снимках относятся к моменту измерения; повторная cache-сборка может создать другой manifest index с тем же содержимым файлов и конфигурацией.

## Что действительно проверено

| Проверка | Полученный результат | Доказательство |
| --- | --- | --- |
| Сборка baseline | Успешна, тот же CRA blog + Express | [Финальная baseline-сборка](evidence/baseline-build.txt) |
| Сборка optimized | Успешна, три стадии, final Alpine | [Финальная сборка](evidence/optimized-build.txt) |
| Серверные HTTP-тесты | **6 passed, 0 failed**, внутри Linux baseline image | [server-tests.txt](evidence/server-tests.txt) |
| Корень `/`, baseline и optimized | HTTP 200, production `index.html` | [baseline](evidence/baseline-http-home.json), [optimized](evidence/optimized-http-home.json) |
| `/api/health`, оба варианта | HTTP 200, JSON `status=ok` | [baseline](evidence/baseline-http-health.json), [optimized](evidence/optimized-http-health.json) |
| `/api/posts`, оба варианта | HTTP 200, три статьи | [baseline](evidence/baseline-http-posts.json), [optimized](evidence/optimized-http-posts.json) |
| SPA route `/posts/1` | HTTP 200, тот же HTML | [optimized SPA](evidence/optimized-http-spa.json) |
| CRA JavaScript и CSS | HTTP 200, непустые assets, корректный content type и SHA-256 | [baseline assets](evidence/baseline-http-assets.json), [optimized assets](evidence/optimized-http-assets.json) |
| Non-root | `uid=1000(node) gid=1000(node)` | [identity](evidence/optimized-identity.txt) |
| Docker healthcheck | `Status: healthy`, exit code 0 | [healthcheck](evidence/optimized-healthcheck.json.txt) |
| Graceful shutdown | После SIGTERM оба процесса завершились с exit code 0 | [baseline](evidence/baseline-stopped-state.json.txt), [optimized](evidence/optimized-stopped-state.json.txt) |
| Baseline сохраняет build tools | Присутствуют make, g++ и frontend react-scripts | [baseline build tools](evidence/baseline-build-tools.txt) |
| Runtime не содержит frontend toolchain | Нет `/app/client` и react-scripts | [runtime contents](evidence/optimized-runtime-contents.txt) |
| Минимальный Node runtime | Node запускается; musl, libstdc++, libgcc разрешаются; npm и headers отсутствуют | [runtime check](evidence/minimal-runtime-check.txt) |
| Исходящий HTTPS после strip | `https://registry.npmjs.org/express` вернул HTTP 200 | [TLS check](evidence/runtime-tls-check.txt) |
| Повторная сборка без изменений | Cache hits, 1.06 сек в данном запуске | [cached build](evidence/optimized-cached-build.txt) |
| Изменение только React-исходника | Слой frontend `npm ci` остался `CACHED`; исходник восстановлен | [source change build](evidence/optimized-source-change-build.txt), [assertion](evidence/source-change-cache-check.json) |
| Реальный Chromium | **6 browser checks passed**, ошибок JavaScript нет | [browser-check.json](evidence/screenshots/browser-check.json) |
| Итоговая уборка | Контейнеров с меткой `devops.lab=5` не осталось | [docker ps output](evidence/remaining-lab5-containers.txt), [остановка screenshot-контейнера](evidence/screenshot-container-stop.txt) |

Тесты дополнительно проверяют JSON 404 для отсутствующего API, SPA fallback, JavaScript content type и 404 для отсутствующего asset вместо ложного HTML-ответа. Итог скрипта: [result.json — status passed](evidence/result.json). Все команды финального автоматического прогона, exit codes и длительности: [commands.json](evidence/commands.json).

## Как получено уменьшение

Baseline — честный single-stage образ на полном `node:24`, без специально добавленных файлов-заполнителей. В нём остаются Debian userland, build tools, исходники frontend, frontend `node_modules`, npm cache и production build. Он успешно обслужил тот же API и те же статические файлы.

Итоговый Dockerfile:

1. Собирает CRA frontend в `react-build` на Node 24.
2. Устанавливает Express production-зависимости в `production-deps` на official `node:24-alpine`.
3. Удаляет ненужные ELF-символы Node через `strip --strip-unneeded` во временной стадии. Размер binary уменьшился с **128 180 080** до **109 377 592** байт. Сам Node после strip запускается как v24.22.2.
4. Создаёт runtime на Alpine 3.24 с libstdc++, libgcc и CA-сертификатами; переносит только Node binary, production `node_modules`, код сервера и готовую статику.
5. Запускает Express от пользователя `node`, UID 1000, через exec-form CMD. Npm, Yarn, Node headers и binutils в final не переносятся.

Точные строки до/после strip находятся в [исходном логе выполнения strip](evidence/attempt-3-before-content-correction/optimized-build.txt); финальная сборка переиспользовала этот неизменный шаг из кеша. Структура истории: [optimized-history.txt](evidence/optimized-history.txt). Копирование frontend касается статических HTML/CSS/JS, а не переноса glibc native modules в musl runtime.

## Первоначальные ошибки и исправления

| Попытка | Результат | Действие |
| --- | --- | --- |
| До запуска Engine | `Server:null`, socket Docker отсутствовал | Docker Desktop запущен основным агентом, повторная проверка дала работающий Engine |
| №1: final `node:24-alpine` | **247 776 149 байт**, 8.73×; критерий `<200 MB` упал | Выяснено, что сама актуальная Node Alpine основа занимала 238 265 905 байт по выбранной метрике |
| №2: только Node binary + deps на Alpine | **201 935 144 байт**, 10.71×; всё ещё выше строгих 200 MB | Дополнительно удалены ненужные ELF-символы binary в промежуточной стадии |
| №3: минимальный runtime + strip | **178 782 076 байт**, 12.09× | Полный финальный прогон прошёл |

Первые неуспешные размеры и assertions сохранены, а не заменены успешными: [attempt-1](evidence/attempt-1/sizes.json), [ошибка №1](evidence/attempt-1/verification-error.txt), [attempt-2](evidence/attempt-2/sizes.json), [ошибка №2](evidence/attempt-2/verification-error.txt). Там же находятся соответствующие Dockerfile и build logs. Эти два прогона остановились на числовом критерии до запуска runtime HTTP-проверок; функциональные результаты таблицы выше получены успешным финальным прогоном.

После первого успешного runtime-прогона исправлены hero-схема и две статьи блога: они теперь описывают фактические три стадии и создание пользователя в чистой Alpine. Первый успешный снимок до этой правки сохранён в `evidence/attempt-3-before-content-correction/`; его размер был 178 781 599 байт. После правки оба образа пересобраны и весь verify повторён с результатом `passed`. Финальные числа находятся в начале этого отчёта.

CRA dependency resolution заняло около 6 минут; конечный lock согласован, TypeScript 4.9.5, `--legacy-peer-deps` не потребовался. Предупреждения о deprecated frontend-пакетах сохранены в первоначальном build log. CRA выбран ради требования задания и не объявляется рекомендуемым стартом нового production-проекта. Аудит уязвимостей и публичное развёртывание этой работой не заявляются.

## Команды и границы результата

Основная воспроизводимая команда из каталога работы:

```bash
node scripts/verify.mjs
```

Она выполняет только локальные build/run/inspect/test/cache операции. Дополнительные setup-команды и первый сбой Engine перечислены в [setup-notes.txt](evidence/setup-notes.txt). Два image tags сохранены для повторного просмотра; временный cache-check tag удалён. Публикация Docker Hub, создание аккаунтов и работа с чужими ресурсами не выполнялись.

Финальный образ отдельно проверен в настоящем Chromium **4 ноября 2026, 12:26 по Бишкеку**. Успешны загрузка трёх статей через живой API, поиск, пустое состояние, фильтр категории, открытие/закрытие статьи и mobile layout без горизонтального переполнения. JavaScript page errors: **0**. Код проверки: [browser-check.cjs](scripts/browser-check.cjs).

Реальные скриншоты: [desktop](evidence/screenshots/blog-desktop.png), [mobile](evidence/screenshots/blog-mobile.png), [открытая статья](evidence/screenshots/blog-article.png). Изображения не генерировались и не подменяли результаты выполнения. Учебная схема и тексты соответствуют фактическим трём стадиям Dockerfile.

После browser capture screenshot-контейнер остановлен и автоматически удалён. Проверка `docker ps -a --filter label=devops.lab=5` не вернула контейнеров. Образы baseline и optimized сохранены. Изменение manifest index после cache replay отдельно сверено: файловые слои и runtime configuration совпадают с протестированным образом, размер тот же — [сравнение payload](evidence/final-payload-comparison.json).
