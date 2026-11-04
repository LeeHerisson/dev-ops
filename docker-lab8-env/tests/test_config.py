import unittest
from config import load_config


def valid(**changes):
    values = {"APP_ENV": "development", "DEBUG": "false", "DB_HOST": "db", "DB_PORT": "5432",
              "DB_NAME": "testdb", "DB_USER": "testuser", "DB_PASSWORD": "private-db-value",
              "SECRET_KEY": "private-key-value"}
    values.update(changes)
    return values


class ConfigurationTests(unittest.TestCase):
    def test_false_is_not_treated_as_truthy_string(self):
        self.assertFalse(load_config(valid(DEBUG="false")).debug)

    def test_true_is_boolean(self):
        self.assertTrue(load_config(valid(DEBUG="true")).debug)

    def test_missing_names_are_reported_without_secret_values(self):
        with self.assertRaises(ValueError) as caught:
            load_config({"DB_PASSWORD": "do-not-expose"})
        self.assertIn("DB_HOST", str(caught.exception))
        self.assertIn("SECRET_KEY", str(caught.exception))
        self.assertNotIn("do-not-expose", str(caught.exception))

    def test_invalid_debug_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "DEBUG"):
            load_config(valid(DEBUG="maybe"))

    def test_invalid_port_is_rejected(self):
        for port in ("abc", "0", "65536", "-1"):
            with self.subTest(port=port), self.assertRaisesRegex(ValueError, "DB_PORT"):
                load_config(valid(DB_PORT=port))

    def test_production_cannot_enable_debug(self):
        with self.assertRaisesRegex(ValueError, "DEBUG"):
            load_config(valid(APP_ENV="production", DEBUG="true"))

    def test_environment_must_be_known(self):
        with self.assertRaisesRegex(ValueError, "APP_ENV"):
            load_config(valid(APP_ENV="prodution"))

    def test_config_repr_does_not_include_secrets(self):
        config = load_config(valid())
        self.assertNotIn("private-db-value", repr(config))
        self.assertNotIn("private-key-value", repr(config))


if __name__ == "__main__":
    unittest.main()
