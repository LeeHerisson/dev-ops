"""The same image is started with independent development/production environments."""
from contextlib import closing
import psycopg2
from flask import Flask, jsonify
from config import load_config


def create_app(configuration=None, connector=None):
    config = configuration or load_config()
    connect = connector or psycopg2.connect
    app = Flask(__name__)
    app.config.update(SECRET_KEY=config.secret_key, DEBUG=config.debug)

    @app.get("/")
    def home():
        return jsonify(message="Config API", environment=config.environment,
                       debug=config.debug, database_host=config.db_host)

    @app.get("/db-test")
    def db_test():
        try:
            with closing(connect(host=config.db_host, port=config.db_port,
                                 dbname=config.db_name, user=config.db_user,
                                 password=config.db_password, connect_timeout=3)) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version(), current_database(), current_user")
                    version, database, user = cursor.fetchone()
            return jsonify(status="success", database_version=version,
                           database=database, database_user=user)
        except psycopg2.Error:
            # Do not return connection strings, passwords or full driver errors.
            app.logger.error("Database connectivity check failed")
            return jsonify(status="error", error="database unavailable"), 503

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=application.config["DEBUG"],
                    use_reloader=False)
