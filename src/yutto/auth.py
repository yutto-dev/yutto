from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, TypedDict

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError

from yutto.cli.settings import xdg_config_home

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

if TYPE_CHECKING:
    from argparse import Namespace
    from pathlib import Path

PROFILE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class AuthInfo(TypedDict):
    SESSDATA: str
    bili_jct: str | None


class AuthProfileModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    sessdata: str = Field(validation_alias=AliasChoices("sessdata", "SESSDATA"))
    bili_jct: str | None = None
    updated_at: str | None = None


class AuthFileModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    profiles: dict[str, AuthProfileModel] = Field(default_factory=dict)


def parse_auth_inline(auth: str) -> AuthInfo | None:
    cookies: dict[str, str] = {}
    for part in auth.split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        cookies[key.strip().lower()] = value.strip()

    sessdata = cookies.get("sessdata")
    if not sessdata:
        return None
    bili_jct = cookies.get("bili_jct")
    return AuthInfo(SESSDATA=sessdata, bili_jct=bili_jct or None)


def format_auth_inline(sessdata: str, bili_jct: str) -> str:
    if bili_jct:
        return f"SESSDATA={sessdata}; bili_jct={bili_jct}"
    return f"SESSDATA={sessdata}"


def default_auth_file() -> Path:
    return xdg_config_home() / "yutto" / "auth.toml"


def resolve_auth_file(args: Namespace) -> Path:
    if args.auth_config is not None:
        return args.auth_config
    return default_auth_file()


def validate_profile(profile: str):
    if not PROFILE_RE.match(profile):
        raise ValueError(f"auth profile 名称不合法：{profile}")


def load_auth(auth_file: Path, profile: str) -> AuthInfo | None:
    validate_profile(profile)
    if not auth_file.exists():
        return None

    try:
        auth_file_model = AuthFileModel.model_validate(tomllib.loads(auth_file.read_text(encoding="utf-8")))
    except (ValidationError, ValueError):
        return None

    entry = auth_file_model.profiles.get(profile)
    if entry is None:
        return None
    if not entry.sessdata:
        return None
    return AuthInfo(SESSDATA=entry.sessdata, bili_jct=entry.bili_jct or None)


def save_auth(auth_file: Path, profile: str, sessdata: str, bili_jct: str | None):
    validate_profile(profile)
    auth_file.parent.mkdir(parents=True, exist_ok=True)

    profiles: dict[str, AuthProfileModel] = {}
    if auth_file.exists():
        try:
            loaded = AuthFileModel.model_validate(tomllib.loads(auth_file.read_text(encoding="utf-8")))
            profiles = dict(loaded.profiles)
        except (ValidationError, ValueError):
            profiles = {}

    original_entry = profiles.get(profile)
    entry_payload: dict[str, Any] = {}
    if original_entry is not None:
        entry_payload = original_entry.model_dump(exclude_none=True)

    entry_payload["sessdata"] = sessdata
    if bili_jct is not None:
        entry_payload["bili_jct"] = bili_jct
    entry_payload["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    profiles[profile] = AuthProfileModel.model_validate(entry_payload)

    lines: list[str] = []
    for profile_name in sorted(profiles.keys()):
        profile_entry_dict = profiles[profile_name].model_dump(exclude_none=True)
        lines.append(f"[profiles.{profile_name}]")
        for key, value in profile_entry_dict.items():
            if isinstance(value, str):
                lines.append(f'{key} = "{escape_toml_basic_string(value)}"')
        lines.append("")

    auth_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    if os.name != "nt":
        auth_file.chmod(0o600)


def save_sessdata(auth_file: Path, profile: str, sessdata: str):
    save_auth(auth_file, profile, sessdata, None)


def escape_toml_basic_string(raw: str) -> str:
    return raw.replace("\\", "\\\\").replace('"', '\\"')
