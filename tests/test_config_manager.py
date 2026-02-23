"""Tests for BlackRoad Config Manager"""
import pytest
from config_manager import ConfigStore, ConfigSchema, ConfigEntry


@pytest.fixture
def store():
    return ConfigStore(env="test", db_path=":memory:")


class TestConfigSchema:
    def test_validate_required_missing(self):
        schema = ConfigSchema("host", "str", required=True)
        err = schema.validate_value(None)
        assert err is not None
        assert "required" in err

    def test_validate_type_int(self):
        schema = ConfigSchema("port", "int")
        assert schema.validate_value("not_a_number") is not None
        assert schema.validate_value("8080") is None

    def test_validate_type_bool(self):
        schema = ConfigSchema("debug", "bool")
        assert schema.validate_value("true") is None
        assert schema.validate_value("invalid_bool_xyz") is not None

    def test_validate_regex(self):
        schema = ConfigSchema("email", "str", validation_regex=r"^[^@]+@[^@]+\.[^@]+$")
        assert schema.validate_value("user@example.com") is None
        assert schema.validate_value("not-an-email") is not None

    def test_validate_json(self):
        schema = ConfigSchema("data", "json")
        assert schema.validate_value('{"key": "val"}') is None
        assert schema.validate_value("not json {") is not None


class TestDefineAndGet:
    def test_define_sets_default(self, store):
        store.define("log_level", "str", default="INFO")
        assert store.get("log_level") == "INFO"

    def test_set_and_get(self, store):
        store.define("port", "int", default=3000)
        store.set("port", 8080)
        assert store.get("port") == 8080

    def test_get_missing_returns_none(self, store):
        assert store.get("nonexistent_key") is None

    def test_type_coercion_int(self, store):
        store.define("workers", "int", default=1)
        store.set("workers", "4")
        assert store.get("workers") == 4

    def test_type_coercion_bool(self, store):
        store.define("debug", "bool", default=False)
        store.set("debug", "true")
        assert store.get("debug") is True

    def test_type_coercion_json(self, store):
        store.define("tags", "json", default=[])
        store.set("tags", '["a","b"]')
        result = store.get("tags")
        assert isinstance(result, list)
        assert "a" in result


class TestCascade:
    def test_override_wins_over_default(self, store):
        store.define("timeout", "int", default=30)
        store.set("timeout", 60, source="override")
        assert store.get("timeout") == 60

    def test_env_var_wins_over_file(self, store):
        store.set("host", "from-file", source="file")
        store.set("host", "from-env", source="env-var")
        assert store.get("host") == "from-env"

    def test_override_wins_over_env_var(self, store):
        store.set("host", "from-env", source="env-var")
        store.set("host", "from-override", source="override")
        assert store.get("host") == "from-override"


class TestEnvOverride:
    def test_env_specific_override(self, store):
        store.define("db_url", "str", default="sqlite:///:memory:")
        store.env_override("db_url", "production", "postgres://prod-server/db")
        assert store.get("db_url", "production") == "postgres://prod-server/db"
        assert store.get("db_url", "test") == "sqlite:///:memory:"

    def test_get_all(self, store):
        store.define("a", "str", default="1")
        store.define("b", "int", default=2)
        all_cfg = store.get_all()
        assert "a" in all_cfg
        assert "b" in all_cfg


class TestValidation:
    def test_validate_no_errors(self, store):
        store.define("host", "str", required=True)
        store.set("host", "localhost")
        errors = store.validate()
        assert errors == []

    def test_validate_missing_required(self, store):
        store.define("secret_key", "str", required=True)
        errors = store.validate()
        assert len(errors) > 0

    def test_validate_multiple_errors(self, store):
        store.define("x", "str", required=True)
        store.define("y", "str", required=True)
        errors = store.validate()
        assert len(errors) >= 2


class TestExport:
    def test_export_env_format(self, store):
        store.define("port", "int", default=8080)
        env_str = store.export_env()
        assert "PORT=8080" in env_str

    def test_export_yaml_format(self, store):
        store.define("port", "int", default=8080)
        yaml_str = store.export_yaml()
        assert "port" in yaml_str
        assert "config:" in yaml_str

    def test_diff_envs(self, store):
        store.define("db_url", "str", default="sqlite:///:memory:")
        store.env_override("db_url", "staging", "postgres://staging/db")
        store.env_override("db_url", "production", "postgres://prod/db")
        diff = store.diff("staging", "production")
        assert "db_url" in diff


class TestAuditLog:
    def test_audit_log_records_changes(self, store):
        store.define("level", "str", default="DEBUG")
        store.set("level", "INFO", source="override")
        store.set("level", "WARN", source="override")
        log = store.audit_log("level")
        assert len(log) >= 1

    def test_audit_log_has_old_and_new(self, store):
        store.define("x", "str", default="a")
        store.set("x", "b", source="override")
        store.set("x", "c", source="override")
        log = store.audit_log("x")
        most_recent = log[0]
        assert most_recent["new_value"] == "c"
