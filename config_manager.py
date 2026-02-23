"""
BlackRoad Config Manager - Hierarchical configuration with environments and overrides
"""
from __future__ import annotations
import json
import re
import os
import sqlite3
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)

CONFIG_TYPES = {"str", "int", "float", "bool", "json"}
SOURCE_PRIORITY = {"default": 0, "file": 1, "env-var": 2, "override": 3}


@dataclass
class ConfigSchema:
    key: str
    type: str
    required: bool = False
    default: Any = None
    description: str = ""
    validation_regex: str = ""

    def validate_value(self, value: Any) -> Optional[str]:
        if value is None:
            if self.required:
                return f"Key '{self.key}' is required"
            return None
        if self.type == "int":
            try:
                int(value)
            except (ValueError, TypeError):
                return f"Key '{self.key}' must be an integer, got {type(value).__name__}"
        elif self.type == "float":
            try:
                float(value)
            except (ValueError, TypeError):
                return f"Key '{self.key}' must be a float"
        elif self.type == "bool":
            if not isinstance(value, bool) and str(value).lower() not in ("true", "false", "1", "0"):
                return f"Key '{self.key}' must be a boolean"
        elif self.type == "json":
            if isinstance(value, str):
                try:
                    json.loads(value)
                except (ValueError, TypeError):
                    return f"Key '{self.key}' must be valid JSON"
        if self.validation_regex and isinstance(value, str):
            if not re.match(self.validation_regex, value):
                return f"Key '{self.key}' does not match pattern '{self.validation_regex}'"
        return None


@dataclass
class ConfigEntry:
    key: str
    value: Any
    type: str
    env: str
    source: str
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def coerce(self) -> Any:
        if self.value is None:
            return None
        if self.type == "int":
            return int(self.value)
        if self.type == "float":
            return float(self.value)
        if self.type == "bool":
            if isinstance(self.value, bool):
                return self.value
            return str(self.value).lower() in ("true", "1", "yes")
        if self.type == "json":
            if isinstance(self.value, str):
                return json.loads(self.value)
            return self.value
        return str(self.value)


class ConfigStore:
    """Hierarchical config store with environment cascade."""

    CASCADE = ["default", "file", "env-var", "override"]

    def __init__(self, env: str = "development", db_path: str = ":memory:"):
        self.env = env
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
        self._schemas: Dict[str, ConfigSchema] = {}

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS config_entries (
                key        TEXT NOT NULL,
                env        TEXT NOT NULL,
                source     TEXT NOT NULL,
                value      TEXT,
                type       TEXT NOT NULL DEFAULT 'str',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (key, env, source)
            );
            CREATE TABLE IF NOT EXISTS schemas (
                key              TEXT PRIMARY KEY,
                type             TEXT NOT NULL,
                required         INTEGER NOT NULL DEFAULT 0,
                default_value    TEXT,
                description      TEXT,
                validation_regex TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                key        TEXT NOT NULL,
                env        TEXT NOT NULL,
                source     TEXT NOT NULL,
                old_value  TEXT,
                new_value  TEXT,
                changed_at TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def define(
        self,
        key: str,
        type: str = "str",
        required: bool = False,
        default: Any = None,
        description: str = "",
        validation_regex: str = "",
    ) -> ConfigSchema:
        schema = ConfigSchema(
            key=key, type=type, required=required,
            default=default, description=description,
            validation_regex=validation_regex,
        )
        self._schemas[key] = schema
        self.conn.execute(
            "INSERT OR REPLACE INTO schemas (key, type, required, default_value, description, validation_regex) VALUES (?,?,?,?,?,?)",
            (key, type, 1 if required else 0, str(default) if default is not None else None, description, validation_regex),
        )
        self.conn.commit()
        if default is not None:
            self.set(key, default, source="default", env="*")
        return schema

    def set(self, key: str, value: Any, source: str = "override", env: Optional[str] = None) -> None:
        env = env or self.env
        schema = self._schemas.get(key)
        type_name = schema.type if schema else "str"
        old_row = self.conn.execute(
            "SELECT value FROM config_entries WHERE key=? AND env=? AND source=?", (key, env, source)
        ).fetchone()
        old_val = old_row[0] if old_row else None
        self.conn.execute(
            "INSERT OR REPLACE INTO config_entries (key, env, source, value, type, updated_at) VALUES (?,?,?,?,?,?)",
            (key, env, source, str(value) if value is not None else None, type_name, datetime.utcnow().isoformat()),
        )
        self.conn.execute(
            "INSERT INTO audit_log (key, env, source, old_value, new_value, changed_at) VALUES (?,?,?,?,?,?)",
            (key, env, source, old_val, str(value) if value is not None else None, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def get(self, key: str, env: Optional[str] = None) -> Any:
        env = env or self.env
        best_value = None
        best_priority = -1
        for source in self.CASCADE:
            for e in [env, "*"]:
                row = self.conn.execute(
                    "SELECT value, type FROM config_entries WHERE key=? AND env=? AND source=?",
                    (key, e, source),
                ).fetchone()
                if row is not None:
                    priority = SOURCE_PRIORITY.get(source, 0)
                    if priority > best_priority:
                        best_priority = priority
                        entry = ConfigEntry(
                            key=key, value=row[0], type=row[1],
                            env=e, source=source,
                        )
                        best_value = entry.coerce()
        if best_value is None:
            schema = self._schemas.get(key)
            if schema and schema.default is not None:
                return schema.default
        return best_value

    def get_all(self, env: Optional[str] = None) -> Dict[str, Any]:
        env = env or self.env
        keys = set()
        for row in self.conn.execute("SELECT DISTINCT key FROM config_entries").fetchall():
            keys.add(row[0])
        for row in self.conn.execute("SELECT key FROM schemas").fetchall():
            keys.add(row[0])
        return {k: self.get(k, env) for k in sorted(keys)}

    def env_override(self, key: str, env: str, value: Any) -> None:
        self.set(key, value, source="override", env=env)

    def load_from_env_vars(self, prefix: str = "APP_") -> int:
        count = 0
        for env_key, env_val in os.environ.items():
            if env_key.startswith(prefix):
                cfg_key = env_key[len(prefix):].lower()
                self.set(cfg_key, env_val, source="env-var", env=self.env)
                count += 1
        return count

    def validate(self) -> List[str]:
        errors = []
        for key, schema in self._schemas.items():
            value = self.get(key)
            err = schema.validate_value(value)
            if err:
                errors.append(err)
        return errors

    def export_env(self, env: Optional[str] = None) -> str:
        env = env or self.env
        config = self.get_all(env)
        lines = [f"# Config export: {env} @ {datetime.utcnow().isoformat()}"]
        for k, v in sorted(config.items()):
            if v is None:
                lines.append(f"# {k.upper()}=")
            elif isinstance(v, (dict, list)):
                lines.append(f"{k.upper()}={json.dumps(v)}")
            else:
                lines.append(f"{k.upper()}={v}")
        return "\n".join(lines)

    def export_yaml(self, env: Optional[str] = None) -> str:
        env = env or self.env
        config = self.get_all(env)
        lines = [f"# Config export: {env}", f"environment: {env}", "config:"]
        for k, v in sorted(config.items()):
            if isinstance(v, (dict, list)):
                lines.append(f"  {k}: {json.dumps(v)}")
            elif isinstance(v, str):
                lines.append(f"  {k}: '{v}'")
            elif v is None:
                lines.append(f"  {k}: null")
            else:
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def diff(self, env1: str, env2: str) -> Dict[str, Dict]:
        all_keys = set()
        for row in self.conn.execute("SELECT DISTINCT key FROM config_entries").fetchall():
            all_keys.add(row[0])
        result = {}
        for key in sorted(all_keys):
            v1 = self.get(key, env1)
            v2 = self.get(key, env2)
            if v1 != v2:
                result[key] = {"env1": v1, "env2": v2}
        return result

    def audit_log(self, key: str) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT key, env, source, old_value, new_value, changed_at FROM audit_log WHERE key=? ORDER BY id DESC",
            (key,),
        ).fetchall()
        return [
            {"key": r[0], "env": r[1], "source": r[2], "old_value": r[3], "new_value": r[4], "changed_at": r[5]}
            for r in rows
        ]

    def get_schema(self, key: str) -> Optional[ConfigSchema]:
        return self._schemas.get(key)

    def list_keys(self) -> List[str]:
        keys = set()
        for row in self.conn.execute("SELECT DISTINCT key FROM config_entries").fetchall():
            keys.add(row[0])
        for row in self.conn.execute("SELECT key FROM schemas").fetchall():
            keys.add(row[0])
        return sorted(keys)

    def delete(self, key: str, env: Optional[str] = None, source: str = "override") -> bool:
        env = env or self.env
        cur = self.conn.execute(
            "DELETE FROM config_entries WHERE key=? AND env=? AND source=?", (key, env, source)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def reset_env(self, env: str) -> int:
        cur = self.conn.execute(
            "DELETE FROM config_entries WHERE env=? AND source NOT IN ('default')", (env,)
        )
        self.conn.commit()
        return cur.rowcount
