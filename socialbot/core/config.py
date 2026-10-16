"""Loads config.yaml, outlets.yaml and .env. Settings live in YAML; secrets live in .env."""

from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


class ConfigError(Exception):
    pass


def _read_yaml(path: Path, what: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise ConfigError(f"Can't find {what}: {path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"{path.name} has a formatting problem (often a missing quote or bad indent):\n{e}")


def load_config(path: Path | None = None) -> dict:
    load_dotenv(ROOT / ".env")
    cfg = _read_yaml(path or ROOT / "config.yaml", "the settings file")
    for key in ("paths", "llm", "news"):
        if key not in cfg:
            raise ConfigError(f"config.yaml is missing the '{key}' section")
    data_dir = Path(cfg["paths"]["data_dir"])
    cfg["paths"]["data_dir"] = data_dir if data_dir.is_absolute() else ROOT / data_dir
    cfg["outlets"] = load_outlets(ROOT / cfg["news"].get("outlets_file", "outlets.yaml"))
    return cfg


def load_outlets(path: Path) -> dict:
    """Returns {"tiers": {tier: {weight, label}}, "by_domain": {domain: outlet}}.
    Domains are stored lower-case without a leading "www."."""
    raw = _read_yaml(path, "the outlets file")
    tiers = {str(k): v for k, v in (raw.get("tiers") or {}).items()}
    if "unlisted" not in tiers:
        raise ConfigError("outlets.yaml must define an 'unlisted' tier")
    by_domain = {}
    for o in raw.get("outlets") or []:
        if "domain" not in o or "name" not in o:
            raise ConfigError(f"outlets.yaml: every outlet needs a domain and a name (got {o})")
        tier = str(o.get("tier", "unlisted"))
        if tier not in tiers:
            raise ConfigError(f"outlets.yaml: {o['domain']} has tier '{tier}', which isn't defined under tiers")
        domain = o["domain"].lower().removeprefix("www.")
        by_domain[domain] = {**o, "domain": domain, "tier": tier, "feeds": list(o.get("feeds") or [])}
    return {"tiers": tiers, "by_domain": by_domain}


def tier_weight(cfg: dict, tier: str) -> float:
    tiers = cfg["outlets"]["tiers"]
    return float((tiers.get(tier) or tiers["unlisted"])["weight"])
