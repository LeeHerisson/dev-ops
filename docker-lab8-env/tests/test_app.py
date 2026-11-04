import unittest
from unittest.mock import MagicMock
import psycopg2
from app import create_app
from config import load_config
from test_config import valid


class ApplicationTests(unittest.TestCase):
    def test_home_shows_only_nonsecret_configuration(self):
        client = create_app(load_config(valid())).test_client()
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["environment"], "development")
        self.assertIs(response.json["debug"], False)
        self.assertNotIn("private-db-value", response.get_data(as_text=True))
        self.assertNotIn("private-key-value", response.get_data(as_text=True))

    def test_successful_query_closes_connection_and_reports_database(self):
        connect = MagicMock()
        conn = connect.return_value
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = ("PostgreSQL test", "testdb", "testuser")
        response = create_app(load_config(valid()), connect).test_client().get("/db-test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["database"], "testdb")
        connect.assert_called_once_with(host="db", port=5432, dbname="testdb", user="testuser",
                                        password="private-db-value", connect_timeout=3)
        conn.close.assert_called_once()

    def test_driver_failure_returns_503_without_internal_error(self):
        connect = MagicMock(side_effect=psycopg2.OperationalError("private connection diagnostic"))
        response = create_app(load_config(valid()), connect).test_client().get("/db-test")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {"status": "error", "error": "database unavailable"})
        self.assertNotIn("private", response.get_data(as_text=True))

    def test_connection_is_closed_if_query_fails(self):
        connect = MagicMock()
        conn = connect.return_value
        conn.cursor.return_value.__enter__.return_value.execute.side_effect = psycopg2.OperationalError("failure")
        response = create_app(load_config(valid()), connect).test_client().get("/db-test")
        self.assertEqual(response.status_code, 503)
        conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
