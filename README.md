# DevOps — лабораторные работы

- [Лабораторная №1: Linux CLI](devops-lab1/README.md)
- [Лабораторная №2: Git и DevOps-инфраструктура](devops-lab2/infrastructure/README.md)

Каждая лабораторная хранится в своей папке. Общие GitHub Actions находятся
в `.github/workflows` в корне репозитория.

Для второй лабораторной: [отчёт](devops-lab2/REPORT.md) и
[инструкция по deployment](devops-lab2/DEPLOYMENT.md).

## Docker — оставшиеся лабораторные

QR-генератор находится в существующей папке `qr-generator` и уже выполнен отдельно. Следующие шесть работ размещены по темам; сквозные номера 5–10 используются для навигации, оригинальные номера из методичек указаны в каждом README.

| Работа | Проект | Отчёт |
|---|---|---|
| 5. Оптимизация React + Express | [Запуск](docker-lab5-optimization/README.md) | [Результаты](docker-lab5-optimization/REPORT.md) |
| 6. Магазин и Docker networking | [Запуск](docker-lab6-networking/README.md) | [Результаты](docker-lab6-networking/REPORT.md) |
| 7. PostgreSQL, volumes, backup/restore | [Запуск](docker-lab7-volumes/README.md) | [Результаты](docker-lab7-volumes/REPORT.md) |
| 8. Один образ, dev/prod и env | [Запуск](docker-lab8-env/README.md) | [Результаты](docker-lab8-env/REPORT.md) |
| 9. Compose: API + PostgreSQL + Redis | [Запуск](docker-lab9-compose/README.md) | [Результаты](docker-lab9-compose/REPORT.md) |
| 10. GitHub Actions + Docker | [Запуск](docker-lab10-cicd/README.md) | [Результаты](docker-lab10-cicd/REPORT.md) |

Общий [отчёт с проверками и ссылками CI](DOCKER_LABS_REPORT.md). Внутри проектов есть воспроизводимые проверки и реальные `evidence/`, включая browser screenshots. Публикация в Docker Hub не требуется по уточнению владельца.

Общие workflow остаются в корневой `.github/workflows`. Локальные env-файлы, служебные `.local/` и зависимости исключены через `.git/info/exclude`, как принято в этом репозитории. Реальные пароли не коммитятся. Контекст Docker отдельно ограничивается `.dockerignore`.
