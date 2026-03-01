# blackroad-config-manager

[![PyPI version](https://img.shields.io/pypi/v/blackroad-config-manager.svg)](https://pypi.org/project/blackroad-config-manager/)
[![Python](https://img.shields.io/pypi/pyversions/blackroad-config-manager.svg)](https://pypi.org/project/blackroad-config-manager/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![Tests](https://github.com/BlackRoad-OS/blackroad-config-manager/actions/workflows/test.yml/badge.svg)](https://github.com/BlackRoad-OS/blackroad-config-manager/actions)

> Hierarchical configuration management with environments and overrides — part of the BlackRoad OS developer platform.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Features](#2-features)
3. [Installation](#3-installation)
4. [Quick Start](#4-quick-start)
5. [Environment Cascade](#5-environment-cascade)
6. [API Reference](#6-api-reference)
   - [ConfigStore](#configstore)
   - [ConfigSchema](#configschema)
   - [ConfigEntry](#configentry)
7. [Stripe Integration Example](#7-stripe-integration-example)
8. [Environment Variable Loading](#8-environment-variable-loading)
9. [Export Formats](#9-export-formats)
10. [Diffing Environments](#10-diffing-environments)
11. [Audit Log](#11-audit-log)
12. [Schema Validation](#12-schema-validation)
13. [End-to-End Testing](#13-end-to-end-testing)
14. [Contributing](#14-contributing)
15. [License](#15-license)

---

## 1. Overview

`blackroad-config-manager` is a production-grade, hierarchical configuration store designed for Python applications that run across multiple environments (development, staging, production). It enforces schema validation, type coercion, full audit logging, and environment-scoped overrides — all backed by a lightweight SQLite store.

---

## 2. Features

| Feature | Description |
|---|---|
| 🌿 **Hierarchical Cascade** | Values resolve in priority order: `default → file → env-var → override` |
| 🌍 **Multi-Environment** | Per-environment overrides for `dev`, `staging`, `production`, or any custom name |
| 🔒 **Schema Validation** | Type checking, required fields, and regex pattern enforcement |
| 🔄 **Type Coercion** | Auto-coerce values to `str`, `int`, `float`, `bool`, or `json` |
| 📤 **Export** | Export current config as `.env` file content or YAML |
| 🔍 **Diff** | Compare configuration values across any two environments |
| 📋 **Audit Log** | Full, ordered change history for every key |
| 🗄️ **SQLite-backed** | In-memory or file-backed persistent store |

---

## 3. Installation

**Requires Python 3.8+**

```bash
pip install blackroad-config-manager
```

For development or contribution:

```bash
git clone https://github.com/BlackRoad-OS/blackroad-config-manager.git
cd blackroad-config-manager
pip install -r requirements.txt
```

---

## 4. Quick Start

```python
from config_manager import ConfigStore

# Create a store for the production environment
cfg = ConfigStore(env="production")

# Define your schema
cfg.define("port",   type="int",  required=True, default=8080, description="HTTP port")
cfg.define("debug",  type="bool", default=False)
cfg.define("db_url", type="str",  required=True)

# Set values from different sources
cfg.set("db_url", "postgres://localhost/myapp", source="file")
cfg.env_override("db_url", "production", "postgres://prod-server/myapp")

# Retrieve with automatic cascade resolution
print(cfg.get("port"))    # 8080
print(cfg.get("db_url"))  # postgres://prod-server/myapp

# Validate all required keys
errors = cfg.validate()
assert errors == []

# Export
print(cfg.export_env())   # PORT=8080\nDEBUG=False\n...
print(cfg.export_yaml())  # YAML-formatted config

# Compare environments
diff = cfg.diff("staging", "production")
```

---

## 5. Environment Cascade

Values are resolved from the **highest-priority source that has a value** for a given key and environment. The priority order, lowest to highest, is:

```
default  →  file  →  env-var  →  override
```

A special wildcard environment `"*"` can be used when calling `set()` to apply a value across all environments:

```python
cfg.set("log_level", "INFO", source="file", env="*")
```

---

## 6. API Reference

### ConfigStore

The main entry point for all configuration operations.

#### `ConfigStore(env, db_path)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `env` | `str` | `"development"` | The active environment name |
| `db_path` | `str` | `":memory:"` | SQLite path; use a file path for persistence |

```python
cfg = ConfigStore(env="production", db_path="/var/app/config.db")
```

---

#### `define(key, type, required, default, description, validation_regex) → ConfigSchema`

Register a key in the schema. If a `default` is provided it is stored at source `"default"`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | — | Configuration key name |
| `type` | `str` | `"str"` | One of `str`, `int`, `float`, `bool`, `json` |
| `required` | `bool` | `False` | Fail validation when no value is present |
| `default` | `Any` | `None` | Value used when no other source provides one |
| `description` | `str` | `""` | Human-readable description |
| `validation_regex` | `str` | `""` | Regex pattern the string value must match |

```python
cfg.define("api_key", type="str", required=True, validation_regex=r"^sk_[a-z]+_[A-Za-z0-9]+$")
```

---

#### `set(key, value, source, env)`

Write a value for a key at a specific source and environment.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | — | Configuration key |
| `value` | `Any` | — | Value to store |
| `source` | `str` | `"override"` | One of `default`, `file`, `env-var`, `override` |
| `env` | `str \| None` | active env | Target environment; `"*"` for all environments |

```python
cfg.set("workers", 4, source="file")
```

---

#### `get(key, env) → Any`

Retrieve the resolved value for a key, applying the cascade rules.

```python
value = cfg.get("port")
value = cfg.get("db_url", env="staging")
```

---

#### `get_all(env) → dict`

Return all known keys and their resolved values for an environment.

```python
all_config = cfg.get_all(env="production")
```

---

#### `env_override(key, env, value)`

Shorthand for `set(key, value, source="override", env=env)`.

```python
cfg.env_override("db_url", "production", "postgres://prod/myapp")
```

---

#### `load_from_env_vars(prefix) → int`

Read OS environment variables whose names start with `prefix`, strip the prefix, lower-case the remainder, and store them at source `"env-var"` for the active environment. Returns the number of keys loaded.

```python
count = cfg.load_from_env_vars(prefix="APP_")
```

---

#### `validate() → list[str]`

Run schema validation for all defined keys against the current environment. Returns a list of error strings (empty list means valid).

```python
errors = cfg.validate()
if errors:
    raise RuntimeError(f"Invalid config: {errors}")
```

---

#### `export_env(env) → str`

Return a `.env`-compatible string for the given environment.

```python
dotenv_content = cfg.export_env()
# PORT=8080
# DEBUG=False
# DB_URL=postgres://...
```

---

#### `export_yaml(env) → str`

Return a YAML-formatted string for the given environment.

```python
yaml_content = cfg.export_yaml()
```

---

#### `diff(env1, env2) → dict`

Return a dictionary of keys whose values differ between two environments.

```python
diff = cfg.diff("staging", "production")
# {"db_url": {"env1": "postgres://staging/db", "env2": "postgres://prod/db"}}
```

---

#### `audit_log(key) → list[dict]`

Return the full change history for a key, newest first. Each entry contains `key`, `env`, `source`, `old_value`, `new_value`, `changed_at`.

```python
log = cfg.audit_log("stripe_secret_key")
```

---

#### `list_keys() → list[str]`

Return a sorted list of all known configuration keys.

---

#### `get_schema(key) → ConfigSchema | None`

Return the schema definition for a key, or `None` if not defined.

---

#### `delete(key, env, source) → bool`

Delete a specific entry. Returns `True` if a row was removed.

---

#### `reset_env(env) → int`

Delete all non-default entries for an environment. Returns the number of rows removed.

---

### ConfigSchema

Dataclass holding the definition for one configuration key.

| Field | Type | Description |
|---|---|---|
| `key` | `str` | Key name |
| `type` | `str` | One of `str`, `int`, `float`, `bool`, `json` |
| `required` | `bool` | Whether a missing value is a validation error |
| `default` | `Any` | Default value |
| `description` | `str` | Human-readable description |
| `validation_regex` | `str` | Regex that string values must satisfy |

#### `validate_value(value) → str | None`

Validate a single value against this schema. Returns an error message or `None`.

---

### ConfigEntry

Dataclass representing one stored value.

| Field | Type | Description |
|---|---|---|
| `key` | `str` | Key name |
| `value` | `Any` | Raw stored value |
| `type` | `str` | Type name |
| `env` | `str` | Environment name |
| `source` | `str` | Source name |
| `updated_at` | `str` | ISO 8601 timestamp |

#### `coerce() → Any`

Return the value coerced to the declared type.

---

## 7. Stripe Integration Example

The following example shows how to manage Stripe API keys and webhook secrets across environments using `blackroad-config-manager`.

```python
from config_manager import ConfigStore

cfg = ConfigStore(env="production", db_path="/var/app/config.db")

# Define Stripe keys with strict validation
cfg.define(
    "stripe_secret_key",
    type="str",
    required=True,
    description="Stripe secret API key",
    validation_regex=r"^sk_(test|live)_[A-Za-z0-9]+$",
)
cfg.define(
    "stripe_publishable_key",
    type="str",
    required=True,
    description="Stripe publishable key",
    validation_regex=r"^pk_(test|live)_[A-Za-z0-9]+$",
)
cfg.define(
    "stripe_webhook_secret",
    type="str",
    required=True,
    description="Stripe webhook signing secret",
    validation_regex=r"^whsec_[A-Za-z0-9]+$",
)
cfg.define("stripe_currency", type="str", default="usd")
cfg.define("stripe_max_retries", type="int", default=3)

# Set test keys for development
cfg.env_override("stripe_secret_key",      "development", "sk_test_yourDevSecretKey")
cfg.env_override("stripe_publishable_key", "development", "pk_test_yourDevPublishableKey")
cfg.env_override("stripe_webhook_secret",  "development", "whsec_yourDevWebhookSecret")

# Set live keys for production (typically loaded from OS environment variables)
# export APP_STRIPE_SECRET_KEY=sk_live_...
# export APP_STRIPE_PUBLISHABLE_KEY=pk_live_...
# export APP_STRIPE_WEBHOOK_SECRET=whsec_...
cfg.load_from_env_vars(prefix="APP_")

# Validate before the application starts
errors = cfg.validate()
if errors:
    raise RuntimeError(f"Stripe config is invalid: {errors}")

# Retrieve in application code
import stripe
stripe.api_key = cfg.get("stripe_secret_key")
stripe.max_network_retries = cfg.get("stripe_max_retries")
```

> **Security note:** Never commit live Stripe keys to source control. Always load production secrets through environment variables or a secrets manager.

---

## 8. Environment Variable Loading

OS environment variables are loaded via `load_from_env_vars()`. The prefix is stripped and the remainder is lower-cased to form the config key:

```
APP_PORT=9000  →  key "port"  (source: env-var)
APP_DB_URL=postgres://...  →  key "db_url"  (source: env-var)
```

`env-var` source has higher priority than `file` but lower priority than `override`.

---

## 9. Export Formats

### `.env` format

```python
print(cfg.export_env(env="production"))
# # Config export: production @ 2026-01-01T00:00:00
# DB_URL=postgres://prod-server/myapp
# DEBUG=False
# PORT=8080
```

### YAML format

```python
print(cfg.export_yaml(env="production"))
# # Config export: production
# environment: production
# config:
#   db_url: 'postgres://prod-server/myapp'
#   debug: False
#   port: 8080
```

---

## 10. Diffing Environments

Use `diff()` to identify configuration drift between any two environments before a deployment:

```python
diff = cfg.diff("staging", "production")
for key, values in diff.items():
    print(f"{key}: staging={values['env1']}  production={values['env2']}")
```

---

## 11. Audit Log

Every `set()` call is recorded. Use `audit_log()` to review the history of any key:

```python
log = cfg.audit_log("db_url")
for entry in log:
    print(f"[{entry['changed_at']}] {entry['old_value']} → {entry['new_value']} ({entry['source']})")
```

---

## 12. Schema Validation

Validation is run across all defined keys for the active environment:

```python
errors = cfg.validate()
# ["Key 'db_url' is required", "Key 'port' must be an integer, got str"]
```

Supported types: `str`, `int`, `float`, `bool`, `json`

Regex example — enforce a semantic version format:

```python
cfg.define("app_version", type="str", validation_regex=r"^\d+\.\d+\.\d+$")
```

---

## 13. End-to-End Testing

### Run the test suite

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests with coverage
PYTHONPATH=. pytest tests/ -v --cov=config_manager
```

### E2E smoke test

The following script exercises the full lifecycle — define, set, load env vars, validate, export, diff, audit — from a single entry point:

```python
import os
from config_manager import ConfigStore

os.environ["APP_DB_URL"] = "postgres://localhost/e2e_test"

cfg = ConfigStore(env="staging")

cfg.define("port",   type="int",  required=True, default=8080)
cfg.define("debug",  type="bool", default=False)
cfg.define("db_url", type="str",  required=True)

cfg.load_from_env_vars(prefix="APP_")
cfg.env_override("port", "production", 443)

errors = cfg.validate()
assert errors == [], f"Validation failed: {errors}"
assert cfg.get("port") == 8080
assert cfg.get("port", env="production") == 443
assert cfg.get("db_url") == "postgres://localhost/e2e_test"

env_export = cfg.export_env()
assert "PORT=8080" in env_export

yaml_export = cfg.export_yaml()
assert "port: 8080" in yaml_export

diff = cfg.diff("staging", "production")
assert "port" in diff

log = cfg.audit_log("db_url")
assert len(log) >= 1

print("E2E smoke test passed ✓")
```

---

## 14. Contributing

1. Fork the repository and create a feature branch.
2. Make your changes with tests covering new behavior.
3. Run `PYTHONPATH=. pytest tests/ -v` and ensure all tests pass.
4. Open a pull request against `main` with a clear description of the change.

---

## 15. License

Proprietary — © BlackRoad OS, Inc. All rights reserved.
