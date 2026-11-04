"""Validated runtime configuration; no secrets are read while importing this module."""
from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class Config:
    environment: str
    debug: bool
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    secret_key: str = field(repr=False)


def load_config(environ=None):
    values = os.environ if environ is None else environ
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "SECRET_KEY")
    missing = [name for name in required if not values.get(name, "").strip()]
    if missing:
        raise ValueError("Missing required variables: " + ", ".join(missing))
    raw_debug = values.get("DEBUG", "false").strip().lower()
    if raw_debug not in ("true", "false"):
        raise ValueError("DEBUG must be true or false")
    try:
        port = int(values.get("DB_PORT", "5432"))
    except (TypeError, ValueError) as error:
        raise ValueError("DB_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("DB_PORT must be in 1..65535")
    environment = values.get("APP_ENV", "production").strip()
    if environment not in ("development", "test", "production"):
        raise ValueError("APP_ENV must be development, test or production")
    debug = raw_debug == "true"
    if environment == "production" and debug:
        raise ValueError("DEBUG must be false in production")
    return Config(environment, debug, values["DB_HOST"], port, values["DB_NAME"],
                  values["DB_USER"], values["DB_PASSWORD"], values["SECRET_KEY"])
