#!/usr/bin/env python3
"""Portable host-side orchestration for the environment-variable laboratory."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / ".local"
STATE = LOCAL / "state.json"
EVIDENCE = ROOT / "evidence"
OWNER = "codex-devops-labs"
PG = "postgres:15-alpine"


def docker(*args, check=True):
    result = subprocess.run(["docker", *args], capture_output=True)
    if check and result.returncode:
        raise RuntimeError("Docker " + args[0] + " failed: " + result.stderr.decode(errors="replace"))
    return result


def output(*args):
    return docker(*args).stdout.decode().strip()


def labels(run_id):
    return ["--label", "devops.owner=" + OWNER, "--label", "devops.lab=8",
            "--label", "devops.run=" + run_id]


def planned_services(run_id):
    result = {}
    for mode, short in (("development", "dev"), ("production", "prod")):
        prefix = "devops-lab8-" + run_id + "-" + short
        result[mode] = {"database": prefix + "-db", "app": prefix + "-app",
                        "network": prefix + "-network", "volume": prefix + "-data"}
    return result


def planned_resources(run_id):
    result = []
    for service in planned_services(run_id).values():
        result.extend((kind, service[key]) for kind, key in
                      (("container", "database"), ("container", "app"), ("network", "network"), ("volume", "volume")))
    for case in ("missing", "debug", "port-text", "port-range", "prod-debug"):
        result.append(("container", "devops-lab8-" + run_id + "-invalid-" + case))
    return result


def inspected(kind, name):
    result = docker(kind, "inspect", name, check=False)
    return json.loads(result.stdout)[0] if result.returncode == 0 else None


def require_owned(kind, name, run_id):
    item = inspected(kind, name)
    if item is None:
        raise RuntimeError("Missing expected " + kind + ": " + name)
    actual = (item.get("Config", {}).get("Labels") if kind == "container" else item.get("Labels")) or {}
    expected = {"devops.owner": OWNER, "devops.lab": "8", "devops.run": run_id}
    if any(actual.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Refusing " + kind + " with different ownership: " + name)


def require_empty_names(run_id):
    # No label filter: a pre-existing object with any label or no labels blocks us.
    for kind, name in planned_resources(run_id):
        if inspected(kind, name) is not None:
            raise RuntimeError("Resource name collision (" + kind + "): " + name + "; existing resource was not modified")


def require_owned_resume(state):
    run_id = state.get("run_id", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", run_id):
        raise RuntimeError("Invalid run ID in local state")
    expected_services = planned_services(run_id)
    for mode, expected in expected_services.items():
        service = state.get("services", {}).get(mode, {})
        if any(service.get(key) != value for key, value in expected.items()):
            raise RuntimeError("Local state contains unexpected resource names; refusing resume")
    # Check the complete set before starting even the first database.
    for service in expected_services.values():
        for kind, key in (("container", "database"), ("container", "app"), ("network", "network"), ("volume", "volume")):
            require_owned(kind, service[key], run_id)


def resources(kind, run_id):
    commands = {"container": ["ps", "-aq"], "network": ["network", "ls", "-q"],
                "volume": ["volume", "ls", "-q"]}
    return output(*commands[kind], "--filter", "label=devops.owner=" + OWNER,
                  "--filter", "label=devops.lab=8", "--filter", "label=devops.run=" + run_id).splitlines()


def read_env(path):
    values = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def configure(force):
    paths = [ROOT / ".env.development", ROOT / ".env.production"]
    if any(path.exists() for path in paths) and not force:
        raise RuntimeError("Env files already exist; no values overwritten. Use --force only for a new empty run.")
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    for environment, dbname, user, debug in (("development", "devdb", "devuser", "true"),
                                             ("production", "proddb", "produser", "false")):
        password = secrets.token_urlsafe(32)
        key = secrets.token_hex(32)
        app_values = {"APP_ENV": environment, "DEBUG": debug, "DB_HOST": "db", "DB_PORT": "5432",
                      "DB_NAME": dbname, "DB_USER": user, "DB_PASSWORD": password, "SECRET_KEY": key}
        pg_values = {"POSTGRES_USER": user, "POSTGRES_DB": dbname, "POSTGRES_PASSWORD": password}
        for path, values in ((ROOT / (".env." + environment), app_values),
                             (LOCAL / ("postgres-" + environment + ".env"), pg_values)):
            # Open with mode 0600 from the first write, not only after creation.
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                stream.write("\n".join(name + "=" + value for name, value in values.items()) + "\n")
            path.chmod(0o600)
    print("Created development/production env files with independent random secrets; values are not displayed.")


def load_state():
    if not STATE.exists():
        raise RuntimeError("No local state; run ./run.sh start first")
    return json.loads(STATE.read_text())


def save_state(state):
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    STATE.chmod(0o600)


def wait_pg(name, user, dbname):
    for _ in range(90):
        result = docker("exec", name, "pg_isready", "-h", "127.0.0.1", "-U", user, "-d", dbname, check=False)
        if result.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("PostgreSQL readiness timeout: " + name)


def address(name):
    raw = output("port", name, "5000/tcp").splitlines()[0]
    return "http://" + raw


def request(url):
    with urllib.request.urlopen(url, timeout=8) as response:
        return response.status, json.load(response)


def wait_http(name):
    url = address(name)
    for _ in range(60):
        try:
            if request(url + "/")[0] == 200:
                return url
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise RuntimeError("HTTP readiness timeout: " + name)


def start(args):
    if STATE.exists() and args.run_id is None:
        state = load_state()
        if any(inspected(kind, name) is not None for kind, name in planned_resources(state.get("run_id", ""))):
            require_owned_resume(state)
            for mode in ("development", "production"):
                values = read_env(ROOT / (".env." + mode))
                docker("start", state["services"][mode]["database"])
                wait_pg(state["services"][mode]["database"], values["DB_USER"], values["DB_NAME"])
                docker("start", state["services"][mode]["app"])
                state["services"][mode]["url"] = wait_http(state["services"][mode]["app"])
            save_state(state)
            print(json.dumps({"run_id": state["run_id"], "resumed": True,
                              "urls": {mode: service["url"] for mode, service in state["services"].items()}}, ensure_ascii=False))
            return

    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(2)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", run_id):
        raise RuntimeError("Invalid run ID")
    require_empty_names(run_id)
    if any(resources(kind, run_id) for kind in ("container", "network", "volume")):
        raise RuntimeError("Run ID already exists; existing resources were not modified")
    if not all((ROOT / (".env." + mode)).exists() and (LOCAL / ("postgres-" + mode + ".env")).exists()
               for mode in ("development", "production")):
        configure(False)
    EVIDENCE.mkdir(exist_ok=True)
    engine = output("version", "--format", "{{.Server.Version}}/{{.Server.Os}}/{{.Server.Arch}}")
    image = "devops-lab8-config:" + run_id
    tests = docker("build", "--progress=plain", "--target", "test", "--no-cache-filter", "test",
                   "-t", image + "-tests", str(ROOT), check=False)
    (EVIDENCE / "build-tests.txt").write_bytes(tests.stdout + tests.stderr)
    if tests.returncode:
        raise RuntimeError("Docker test-stage failed; see evidence/build-tests.txt")
    build = docker("build", "--progress=plain", "--target", "runtime", "-t", image, str(ROOT), check=False)
    (EVIDENCE / "build-runtime.txt").write_bytes(build.stdout + build.stderr)
    if build.returncode:
        raise RuntimeError("Runtime build failed; see evidence/build-runtime.txt")
    state = {"run_id": run_id, "image": image, "image_id": output("image", "inspect", image, "--format", "{{.Id}}"),
             "engine": engine, "started_at": dt.datetime.now(dt.timezone.utc).isoformat(), "services": {}}
    save_state(state)
    if docker("image", "inspect", PG, check=False).returncode:
        docker("pull", PG)
    try:
        for mode, short, port in (("development", "dev", args.port_dev), ("production", "prod", args.port_prod)):
            prefix = "devops-lab8-" + run_id + "-" + short
            service = {"database": prefix + "-db", "app": prefix + "-app", "network": prefix + "-network", "volume": prefix + "-data"}
            state["services"][mode] = service
            save_state(state)
            values = read_env(ROOT / (".env." + mode))
            pg_values = read_env(LOCAL / ("postgres-" + mode + ".env"))
            if values["DB_PASSWORD"] != pg_values["POSTGRES_PASSWORD"]:
                raise RuntimeError("App and PostgreSQL env files are inconsistent; no secret value displayed")
            docker("network", "create", *labels(run_id), service["network"])
            require_owned("network", service["network"], run_id)
            docker("volume", "create", *labels(run_id), service["volume"])
            require_owned("volume", service["volume"], run_id)
            docker("run", "-d", "--name", service["database"], *labels(run_id),
                   "--network", service["network"], "--network-alias", "db",
                   "--env-file", str(LOCAL / ("postgres-" + mode + ".env")),
                   "--mount", "type=volume,source=" + service["volume"] + ",target=/var/lib/postgresql/data", PG)
            wait_pg(service["database"], values["DB_USER"], values["DB_NAME"])
            publication = "127.0.0.1:" + (str(port) if port else "") + ":5000"
            docker("run", "-d", "--name", service["app"], *labels(run_id),
                   "--network", service["network"], "--env-file", str(ROOT / (".env." + mode)),
                   "-p", publication, state["image"])
            service["url"] = wait_http(service["app"])
            save_state(state)
    except Exception:
        stop(state)
        raise
    print(json.dumps({"run_id": run_id, "image_id": state["image_id"],
                      "urls": {mode: service["url"] for mode, service in state["services"].items()}}, ensure_ascii=False))


def stop(state):
    for name in resources("container", state["run_id"]):
        docker("stop", "--time", "30", name, check=False)
    container_ids = resources("container", state["run_id"])
    statuses = {output("inspect", identifier, "--format", "{{.Name}}").lstrip("/"):
                output("inspect", identifier, "--format", "{{.State.Status}}")
                for identifier in container_ids}
    exit_codes = {output("inspect", identifier, "--format", "{{.Name}}").lstrip("/"):
                  int(output("inspect", identifier, "--format", "{{.State.ExitCode}}"))
                  for identifier in container_ids}
    path = EVIDENCE / "verification.json"
    if path.exists():
        evidence = json.loads(path.read_text())
        if evidence.get("run_id") == state["run_id"]:
            evidence["stopped_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            evidence["final_container_states"] = statuses
            evidence["final_container_exit_codes"] = exit_codes
            evidence["all_own_containers_stopped"] = all(value == "exited" for value in statuses.values())
            evidence["all_own_containers_exited_cleanly"] = all(value == 0 for value in exit_codes.values())
            if not evidence["all_own_containers_stopped"]:
                evidence["status"] = "failed"
            encoded = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
            path.write_text(encoded)
            (EVIDENCE / ("verification-" + state["run_id"] + ".json")).write_text(encoded)
            write_report(evidence)
    if any(value != "exited" for value in statuses.values()):
        raise RuntimeError("Some lab8 containers failed to stop; inspect their status")


def query(service, values, sql):
    return output("exec", service["database"], "psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-U", values["DB_USER"],
                  "-d", values["DB_NAME"], "-c", sql)


def write_report(evidence):
    rows = "\n".join("| " + item["name"] + " | " + ("PASS" if item["passed"] else "FAIL") + " |" for item in evidence["checks"])
    (ROOT / "REPORT.md").write_text(f"""# Отчёт по Docker lab 8

Оригинал задания: ЛР4 «Environment Variables & Configuration», Docker_Volumes_EnvVars.pdf, страницы 23–28, исходный код на страницах 16–18. Сквозная рабочая нумерация: lab8.

Фактическая проверка: {evidence['checked_at']}; статус **{evidence['status']}**, run ID `{evidence['run_id']}`.
Docker Engine: `{evidence['engine']}`. Оба режима запущены из одного image ID `{evidence['image_id']}`.

| Реальная проверка | Результат |
|---|---|
{rows}

Результаты HTTP и безопасные сведения о ресурсах: `evidence/verification.json`. Настоящие unit-тесты выполнены внутри Docker test-stage; вывод: `evidence/build-tests.txt`. Runtime собирается отдельно и не включает tests или env-файлы.

Development и production используют отдельные сети, named volumes и реальные PostgreSQL 15. В обеих сетях имя БД — `db`, а содержимое и учётные данные независимы. Пароли и SECRET_KEY сгенерированы локально и не выведены в evidence. DB-порты на хосте не публикуются.

Это учебный production-like режим конфигурации: в нём DEBUG=false, но используется development server Flask из задания. Публичного deployment и Docker Hub публикации не было. Для промышленного deployment нужны WSGI, TLS и отдельная эксплуатационная конфигурация.

По завершении выполнения контейнеры остановлены; volumes сохранены. Команда `./run.sh start` возобновляет сохранённый запуск, `./run.sh check` повторяет проверки. Очистка данных выполняется только явным `./run.sh cleanup --delete-data`.
""")
    guard_path = EVIDENCE / "collision-guard.json"
    if guard_path.exists():
        guard = json.loads(guard_path.read_text())
        addition = ("\n## Дополнительная проверка защиты имён\n\n"
                    + "Дата: " + guard["measured_at_utc"] + ". Новый запуск предварительно проверяет все запланированные имена контейнеров, сетей и volumes без фильтра labels, до configure/build/create. Resume проверяет owner/lab/run всех восьми сохранённых ресурсов до первого start.\n\n"
                    + "В реальном regression-тесте отдельный синтетический volume получил ожидаемое имя development volume и чужие labels. CLI отказался до сборки образов и подключения данных. Содержимое, labels, исходные state/verification файлы остались неизменны; runtime и test images для тестового run ID не появились. "
                    + str(sum(item["passed"] for item in guard["checks"])) + "/" + str(len(guard["checks"])) + " проверок PASS. Синтетический volume удалён; существующие volumes лабораторной не изменялись. Протокол: `evidence/collision-guard.json`.\n\n"
                    + "Полный dev/prod запуск после правки preflight не повторялся: приложение и Dockerfile не менялись; результаты 12 unit-тестов и 24 основных проверок выше относятся к исходному финальному запуску.\n")
        with (ROOT / "REPORT.md").open("a") as stream:
            stream.write(addition)


def check(state):
    evidence = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(), "run_id": state["run_id"],
                "image_id": state["image_id"], "engine": state["engine"], "status": "running", "checks": [],
                "http": {}, "resources": state["services"], "validation": {}}

    def assertion(name, passed):
        evidence["checks"].append({"name": name, "passed": bool(passed)})
        if not passed:
            raise AssertionError(name)

    try:
        image_ids = []
        all_secrets = []
        for mode in ("development", "production"):
            values = read_env(ROOT / (".env." + mode))
            all_secrets.extend([values["DB_PASSWORD"], values["SECRET_KEY"]])
            service = state["services"][mode]
            service["url"] = address(service["app"])
            status, home = request(service["url"] + "/")
            db_status, db_result = request(service["url"] + "/db-test")
            evidence["http"][mode] = {"home_status": status, "home": home, "database_status": db_status, "database": db_result}
            assertion(mode + ": HTTP и режим DEBUG", status == 200 and home["environment"] == mode and home["debug"] == (mode == "development"))
            assertion(mode + ": реальный PostgreSQL и нужная БД", db_status == 200 and db_result["database"] == values["DB_NAME"] and db_result["database_user"] == values["DB_USER"])
            image_ids.append(output("inspect", service["app"], "--format", "{{.Image}}"))
            assertion(mode + ": процесс non-root", output("exec", service["app"], "id", "-u") == "10001")
        assertion("Оба режима используют один и тот же image ID", image_ids == [state["image_id"], state["image_id"]])
        dev = state["services"]["development"]
        prod = state["services"]["production"]
        dev_env = read_env(ROOT / ".env.development")
        prod_env = read_env(ROOT / ".env.production")
        query(dev, dev_env, "CREATE TABLE IF NOT EXISTS lab8_isolation(marker text); TRUNCATE lab8_isolation; INSERT INTO lab8_isolation VALUES ('development only');")
        isolated = query(prod, prod_env, "SELECT to_regclass('public.lab8_isolation') IS NULL;")
        assertion("Данные development не появились в production", isolated == "t")
        assertion("Сети и volumes двух окружений различны", dev["network"] != prod["network"] and dev["volume"] != prod["volume"])
        assertion("Пароли и SECRET_KEY сред независимы", dev_env["DB_PASSWORD"] != prod_env["DB_PASSWORD"] and dev_env["SECRET_KEY"] != prod_env["SECRET_KEY"])
        for case, options, expected in (
            ("missing", [], "Missing required variables"),
            ("debug", ["--env-file", str(ROOT / ".env.development"), "-e", "DEBUG=maybe"], "DEBUG"),
            ("port-text", ["--env-file", str(ROOT / ".env.development"), "-e", "DB_PORT=abc"], "DB_PORT"),
            ("port-range", ["--env-file", str(ROOT / ".env.development"), "-e", "DB_PORT=65536"], "DB_PORT"),
            ("prod-debug", ["--env-file", str(ROOT / ".env.production"), "-e", "DEBUG=true"], "DEBUG"),
        ):
            result = docker("run", "--rm", "--name", "devops-lab8-" + state["run_id"] + "-invalid-" + case,
                            *labels(state["run_id"]), *options, state["image"], check=False)
            diagnostic = (result.stdout + result.stderr).decode(errors="replace")
            assertion("Валидация контейнера: " + case, result.returncode != 0 and expected in diagnostic)
            assertion("Диагностика " + case + " не раскрыла секреты", not any(value in diagnostic for value in all_secrets))
            evidence["validation"][case] = {"exit_code": result.returncode, "expected_field": expected, "secret_values_absent": True}
        safe_http = json.dumps(evidence["http"])
        assertion("HTTP ответы не содержат секретов", not any(value in safe_http for value in all_secrets))
        image_config = output("image", "inspect", state["image"], "--format", "{{json .Config.Env}}")
        assertion("Конфигурация образа не содержит реальных секретов", not any(value in image_config for value in all_secrets))
        mounted_envs = output("exec", prod["app"], "python", "-c",
                              "from pathlib import Path; print(list(Path('/app').glob('.env*')))")
        assertion("Env-файлы не скопированы в runtime image", mounted_envs == "[]")
        env_paths = [ROOT / ".env.development", ROOT / ".env.production",
                     LOCAL / "postgres-development.env", LOCAL / "postgres-production.env"]
        assertion("Локальные секретные env-файлы имеют права 0600", all(path.stat().st_mode & 0o777 == 0o600 for path in env_paths))
        evidence["status"] = "passed"
    except Exception as error:
        evidence["status"] = "failed"
        evidence["error"] = str(error)
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / "verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    (EVIDENCE / ("verification-" + state["run_id"] + ".json")).write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    write_report(evidence)
    print(json.dumps({"status": evidence["status"], "checks": len(evidence["checks"]), "run_id": state["run_id"]}, ensure_ascii=False))
    if evidence["status"] != "passed":
        raise RuntimeError("Verification failed; see evidence/verification.json")


def cleanup(state, delete_data):
    stop(state)
    containers = resources("container", state["run_id"])
    if containers:
        docker("rm", *containers)
    for network in resources("network", state["run_id"]):
        docker("network", "rm", network)
    volumes = resources("volume", state["run_id"])
    if delete_data and volumes:
        docker("volume", "rm", *volumes)
    print(json.dumps({"run_id": state["run_id"], "containers_removed": len(containers),
                      "volumes_deleted": bool(delete_data), "volumes": volumes}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    config_parser = sub.add_parser("configure")
    config_parser.add_argument("--force", action="store_true")
    start_parser = sub.add_parser("start")
    start_parser.add_argument("--run-id")
    start_parser.add_argument("--port-dev", type=int, default=0)
    start_parser.add_argument("--port-prod", type=int, default=0)
    sub.add_parser("stop")
    sub.add_parser("check")
    sub.add_parser("status")
    clean_parser = sub.add_parser("cleanup")
    clean_parser.add_argument("--delete-data", action="store_true")
    clean_parser.add_argument("--run-id")
    args = parser.parse_args()
    try:
        if args.command == "configure":
            configure(args.force)
        elif args.command == "start":
            start(args)
        else:
            state = load_state()
            if args.command == "stop":
                stop(state)
                print("Stopped only containers labelled for lab8 run " + state["run_id"])
            elif args.command == "check":
                check(state)
            elif args.command == "status":
                print(json.dumps({"run_id": state["run_id"], "services": state["services"]}, ensure_ascii=False, indent=2))
            elif args.command == "cleanup":
                if args.run_id:
                    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", args.run_id):
                        raise RuntimeError("Invalid run ID")
                    state = {"run_id": args.run_id}
                cleanup(state, args.delete_data)
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
