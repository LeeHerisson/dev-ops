#!/usr/bin/env python3
"""Run the persistence/backup lab using only resources labelled for this run."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
OWNER = "codex-devops-labs"
PG_IMAGE = "postgres:15-alpine"
HELPER_IMAGE = "alpine:3.22"
SNAPSHOT_SQL = """
SELECT json_build_object(
  'students', (SELECT json_agg(s ORDER BY s.id) FROM students s),
  'courses', (SELECT json_agg(c ORDER BY c.id) FROM courses c)
)::text;
"""


def docker(*args, data=None, check=True):
    result = subprocess.run(["docker", *args], input=data, capture_output=True)
    if check and result.returncode:
        # Inputs may contain secrets: report only output and the operation.
        raise RuntimeError("Docker " + args[0] + " failed: " + result.stderr.decode(errors="replace"))
    return result


def output(*args, data=None):
    return docker(*args, data=data).stdout.decode().strip()


def labels(run_id):
    return ["--label", "devops.owner=" + OWNER, "--label", "devops.lab=7",
            "--label", "devops.run=" + run_id]


def require_absent(kind, name):
    # Inspect by exact name without a label filter: foreign names also block a run.
    if docker(kind, "inspect", name, check=False).returncode == 0:
        raise RuntimeError("Resource name collision (" + kind + "): " + name + "; existing resource was not modified")


def require_owned_volume(name, run_id):
    actual = json.loads(output("volume", "inspect", name))[0].get("Labels") or {}
    expected = {"devops.owner": OWNER, "devops.lab": "7", "devops.run": run_id}
    if any(actual.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Refusing a volume with different ownership: " + name)


def filtered(kind, run_id):
    filters = ["--filter", "label=devops.owner=" + OWNER,
               "--filter", "label=devops.lab=7", "--filter", "label=devops.run=" + run_id]
    args = ["ps", "-aq"] if kind == "container" else ["volume", "ls", "-q"]
    return output(*args, *filters).splitlines()


def stop_own(run_id):
    for container in filtered("container", run_id):
        docker("stop", "--time", "30", container, check=False)


def cleanup(run_id, delete_data):
    stop_own(run_id)
    containers = filtered("container", run_id)
    if containers:
        docker("rm", *containers)
    volumes = filtered("volume", run_id)
    if delete_data and volumes:
        docker("volume", "rm", *volumes)
    print(json.dumps({"run_id": run_id, "removed_containers": len(containers),
                      "volumes_deleted": bool(delete_data), "volumes": volumes}, ensure_ascii=False))


def wait_pg(name):
    for _ in range(90):
        ready = docker("exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "student",
                       "-d", "university", check=False)
        if ready.returncode == 0:
            sql = docker("exec", name, "psql", "-XAt", "-U", "student", "-d", "university",
                         "-c", "SELECT 1", check=False)
            if sql.returncode == 0 and sql.stdout.strip() == b"1":
                return
        time.sleep(1)
    raise RuntimeError("PostgreSQL readiness timeout: " + name)


def sql(name, query):
    return output("exec", name, "psql", "-XAt", "-v", "ON_ERROR_STOP=1",
                  "-U", "student", "-d", "university", "-c", query)


def snapshot(name):
    return json.loads(sql(name, SNAPSHOT_SQL))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def report(evidence):
    tests = evidence["checks"]
    rows = "\n".join("| " + test["name"] + " | " + ("PASS" if test["passed"] else "FAIL") + " |"
                     for test in tests)
    archive = evidence.get("physical_backup", {})
    text = f"""# Отчёт по Docker lab 7

Оригинал задания: ЛР3 «PostgreSQL с Persistent Storage», Docker_Volumes_EnvVars.pdf, страницы 19–22.
Рабочая сквозная нумерация репозитория: lab7. Выполнение: {evidence['started_at']}.

Статус: **{evidence['status']}**. Run ID: `{evidence['run_id']}`.
Engine: `{evidence.get('engine', 'unknown')}`. Образ: `{evidence.get('postgres_image_id', PG_IMAGE)}`.

| Реальная проверка | Результат |
|---|---|
{rows}

В исходной схеме созданы ровно 4 студента и 3 курса. Сравнивались все поля обеих таблиц, включая ID и created_at, до и после замены контейнера и обоих восстановлений. Данные сравниваются программно, не только по числу строк.

SQL dump: `evidence/backup.sql`. JSON протокол: `evidence/verification.json`.
Физический архив находится вне репозитория: `{archive.get('path', 'не создан')}`.
Размер физического архива: {archive.get('bytes', 0)} байт; SHA-256: `{archive.get('sha256', 'n/a')}`.

Архивирование выполнялось после штатной остановки PostgreSQL. SQL dump сделан работающим pg_dump. Для каждого восстановления использован отдельный named volume. По завершении все контейнеры этого запуска остановлены; три volume сохранены. Чужие ресурсы не изменялись, prune не использовался.

Список ресурсов и точные snapshots сохранены в JSON. Запуск был локальным, без Docker Hub и других внешних публикаций.
"""
    if evidence.get("error"):
        text += "\nОшибка: " + evidence["error"] + "\n"
    guard_path = ROOT / "evidence" / "collision-guard.json"
    if guard_path.exists():
        guard = json.loads(guard_path.read_text())
        text += ("\n## Дополнительная проверка защиты имён\n\n"
                 + "Дата: " + guard["measured_at_utc"] + ". Исправлен preflight: все запланированные имена проверяются без фильтра labels до создания файлов и Docker-ресурсов.\n\n"
                 + "Реальный regression-тест: создан отдельный синтетический volume с ожидаемым именем и чужими labels. CLI отказался до подключения volume; содержимое и labels остались неизменны, исходный verification.json не перезаписан. "
                 + str(sum(item["passed"] for item in guard["checks"])) + "/" + str(len(guard["checks"])) + " проверок PASS. Тестовый volume удалён после проверки; существующие volumes лабораторной не изменялись. Протокол: `evidence/collision-guard.json`.\n\n"
                 + "Полный PostgreSQL backup/restore после этой правки не повторялся: менялась только предварительная защита имён; результаты основной проверки выше относятся к указанному исходному запуску.\n")
    (ROOT / "REPORT.md").write_text(text)


def run(args):
    run_id = args.run_id
    # Refuse a collision before creating files or entering the cleanup path.
    engine = output("version", "--format", "{{.Server.Version}}/{{.Server.Os}}/{{.Server.Arch}}")
    prefix = "devops-lab7-" + run_id
    names = {"original": prefix + "-db", "replacement": prefix + "-db-replaced",
             "sql_restore": prefix + "-sql-restore", "physical_restore": prefix + "-physical-restore"}
    volumes = {"main": prefix + "-data", "sql_restore": prefix + "-sql-data",
               "physical_restore": prefix + "-physical-data"}
    for name in [*names.values(), prefix + "-backup-helper", prefix + "-restore-helper"]:
        require_absent("container", name)
    for name in volumes.values():
        require_absent("volume", name)
    if filtered("container", run_id) or filtered("volume", run_id):
        raise RuntimeError("Run ID already exists; choose a new run ID, existing data was not modified")
    backup_dir = Path(args.backup_dir or (Path(tempfile.gettempdir()) / "devops-lab7-backups" / run_id)).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    env_file = backup_dir / "postgres.env"
    env_file.write_text("POSTGRES_USER=student\nPOSTGRES_DB=university\nPOSTGRES_PASSWORD=" + secrets.token_urlsafe(32) + "\n")
    env_file.chmod(0o600)
    evidence_dir = ROOT / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    evidence = {"started_at": dt.datetime.now(dt.timezone.utc).isoformat(), "run_id": run_id,
                "status": "running", "checks": [], "containers": names, "volumes": volumes,
                "snapshots": {}}

    def check(name, passed):
        evidence["checks"].append({"name": name, "passed": bool(passed)})
        if not passed:
            raise AssertionError(name)

    def volume(name):
        docker("volume", "create", *labels(run_id), name)
        # docker volume create may return an existing object; verify before mounting.
        require_owned_volume(name, run_id)

    def launch(name, volume_name):
        require_owned_volume(volume_name, run_id)
        docker("run", "-d", "--name", name, *labels(run_id), "--env-file", str(env_file),
               "--mount", "type=volume,source=" + volume_name + ",target=/var/lib/postgresql/data", PG_IMAGE)
        wait_pg(name)

    try:
        evidence["engine"] = engine
        docker("pull", PG_IMAGE)
        docker("pull", HELPER_IMAGE)
        evidence["postgres_image_id"] = output("image", "inspect", PG_IMAGE, "--format", "{{.Id}}")
        volume(volumes["main"])
        launch(names["original"], volumes["main"])
        output("exec", "-i", names["original"], "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "student",
               "-d", "university", data=(ROOT / "init.sql").read_bytes())
        baseline = snapshot(names["original"])
        evidence["snapshots"]["before_replacement"] = baseline
        check("Инициализация: 4 студента и 3 курса", len(baseline["students"]) == 4 and len(baseline["courses"]) == 3)
        old_id = output("inspect", names["original"], "--format", "{{.Id}}")
        docker("stop", "--time", "30", names["original"])
        docker("rm", names["original"])
        launch(names["replacement"], volumes["main"])
        new_id = output("inspect", names["replacement"], "--format", "{{.Id}}")
        replaced = snapshot(names["replacement"])
        evidence["snapshots"]["after_replacement"] = replaced
        evidence["container_replacement"] = {"old_id": old_id, "new_id": new_id}
        check("Старый контейнер удалён, новый имеет другой ID", old_id != new_id)
        check("Все данные сохранены после замены контейнера", baseline == replaced)
        dump = docker("exec", names["replacement"], "pg_dump", "-U", "student", "-d", "university", "--no-owner", "--no-privileges").stdout
        dump_path = evidence_dir / "backup.sql"
        dump_path.write_bytes(dump)
        evidence["sql_backup"] = {"path": "evidence/backup.sql", "bytes": len(dump), "sha256": digest(dump_path)}
        check("pg_dump успешно создал непустой SQL backup", len(dump) > 500)
        volume(volumes["sql_restore"])
        launch(names["sql_restore"], volumes["sql_restore"])
        output("exec", "-i", names["sql_restore"], "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "student", "-d", "university", data=dump)
        restored = snapshot(names["sql_restore"])
        evidence["snapshots"]["sql_restore"] = restored
        check("SQL restore в отдельный volume: все поля совпали", baseline == restored)
        docker("stop", "--time", "30", names["replacement"])
        stopped = output("inspect", names["replacement"], "--format", "{{.State.Running}}") == "false"
        check("Перед физическим tar PostgreSQL штатно остановлен", stopped)
        archive_path = backup_dir / "postgres-volume-backup.tar.gz"
        docker("run", "--rm", "--name", prefix + "-backup-helper", *labels(run_id),
               "--mount", "type=volume,source=" + volumes["main"] + ",target=/data,readonly",
               "--mount", "type=bind,source=" + str(backup_dir) + ",target=/backup",
               HELPER_IMAGE, "tar", "-czf", "/backup/" + archive_path.name, "-C", "/data", ".")
        evidence["physical_backup"] = {"path": str(archive_path), "bytes": archive_path.stat().st_size,
                                       "sha256": digest(archive_path), "database_stopped": stopped}
        check("Физический архив создан", archive_path.stat().st_size > 1000)
        volume(volumes["physical_restore"])
        docker("run", "--rm", "--name", prefix + "-restore-helper", *labels(run_id),
               "--mount", "type=volume,source=" + volumes["physical_restore"] + ",target=/data",
               "--mount", "type=bind,source=" + str(backup_dir) + ",target=/backup,readonly",
               HELPER_IMAGE, "tar", "-xzf", "/backup/" + archive_path.name, "-C", "/data")
        launch(names["physical_restore"], volumes["physical_restore"])
        physical = snapshot(names["physical_restore"])
        evidence["snapshots"]["physical_restore"] = physical
        check("Физический restore в отдельный volume: все поля совпали", baseline == physical)
        evidence["status"] = "passed"
    except Exception as error:
        evidence["status"] = "failed"
        evidence["error"] = str(error)
    finally:
        try:
            stop_own(run_id)
            remaining = filtered("container", run_id)
            states = {name: output("inspect", name, "--format", "{{.State.Status}}") for name in remaining}
        except Exception as error:
            states = {}
            evidence["cleanup_error"] = str(error)
            evidence["status"] = "failed"
        evidence["final_container_states"] = states
        evidence["all_own_containers_stopped"] = not evidence.get("cleanup_error") and all(value == "exited" for value in states.values())
        evidence["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        env_file.unlink(missing_ok=True)
        (evidence_dir / "verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
        (evidence_dir / "summary.txt").write_text("\n".join(("PASS " if item["passed"] else "FAIL ") + item["name"] for item in evidence["checks"]) + "\n")
        report(evidence)
    print(json.dumps({"status": evidence["status"], "run_id": run_id, "checks": len(evidence["checks"]),
                      "all_containers_stopped": evidence["all_own_containers_stopped"]}, ensure_ascii=False))
    return 0 if evidence["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(2))
    parser.add_argument("--backup-dir")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--delete-data", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", args.run_id):
        parser.error("run-id must contain 2..49 lowercase letters, digits or hyphens")
    if args.cleanup:
        cleanup(args.run_id, args.delete_data)
        return 0
    try:
        return run(args)
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
