# blackroad-config-manager

> Hierarchical configuration management with environments and overrides — part of the BlackRoad OS developer platform.

## Features

- 🌿 **Hierarchical Cascade** — default → file → env-var → override
- 🌍 **Multi-Environment** — Per-environment overrides (dev/staging/prod)
- 🔒 **Schema Validation** — Type checking, required fields, regex patterns
- 📤 **Export** — .env and YAML format export
- 🔍 **Diff** — Compare configurations between environments
- 📋 **Audit Log** — Full change history per key
- 🔄 **Type Coercion** — Auto-coerce str/int/float/bool/json values

## Quick Start

```python
from config_manager import ConfigStore

cfg = ConfigStore(env="production")

# Define schema
cfg.define("port", type="int", required=True, default=8080, description="HTTP port")
cfg.define("debug", type="bool", default=False)
cfg.define("db_url", type="str", required=True)

# Set values
cfg.set("db_url", "postgres://localhost/myapp", source="file")
cfg.env_override("db_url", "production", "postgres://prod-server/myapp")

# Get with cascade
print(cfg.get("port"))  # 8080

# Validate
errors = cfg.validate()  # []

# Export
print(cfg.export_env())   # PORT=8080\nDEBUG=False\n...
print(cfg.export_yaml())  # YAML format

# Diff environments
diff = cfg.diff("staging", "production")
```

## Running Tests

```bash
pip install pytest pytest-cov
pytest tests/ -v --cov=config_manager
```

## License

Proprietary — © BlackRoad OS, Inc.
