from __future__ import annotations

import os
import platform
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from argparse import Namespace

PROFILE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def xdg_config_home() -> Path:
    if (env := os.environ.get("XDG_CONFIG_HOME")) and (path := Path(env)).is_absolute():
        return path
    home = Path.home()
    if platform.system() == "Windows":
        return home / "AppData" / "Roaming"
    return home / ".config"


class AuthInfo(TypedDict):
    SESSDATA: str
    bili_jct: str | None
    cookies: NotRequired[dict[str, str]]


class AuthProfileModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    sessdata: str = Field(validation_alias=AliasChoices("sessdata", "SESSDATA"))
    bili_jct: str | None = None
    cookies: dict[str, str] | None = None
    updated_at: str | None = None


class AuthFileModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    profiles: dict[str, AuthProfileModel] = Field(default_factory=dict)


def parse_auth_inline(auth: str) -> AuthInfo | None:
    lowered: dict[str, str] = {}
    names: dict[str, str] = {}
    for part in auth.split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        name = key.strip()
        if not name:
            continue
        lowered[name.lower()] = value.strip()
        # 保留原始大小写的 Cookie 名（后出现的同名键覆盖先出现的）
        names[name.lower()] = name

    sessdata = lowered.get("sessdata")
    if not sessdata:
        return None
    bili_jct = lowered.get("bili_jct")
    auth_info = AuthInfo(SESSDATA=sessdata, bili_jct=bili_jct or None)
    extra = {names[name]: value for name, value in lowered.items() if name not in ("sessdata", "bili_jct") and value}
    if extra:
        auth_info["cookies"] = extra
    return auth_info


def format_auth_inline(sessdata: str, bili_jct: str | None = None) -> str:
    if bili_jct:
        return f"SESSDATA={sessdata}; bili_jct={bili_jct}"
    return f"SESSDATA={sessdata}"


def default_auth_file() -> Path:
    return xdg_config_home() / "yutto" / "auth.toml"


def resolve_auth_file(args: Namespace) -> Path:
    if args.auth_file is not None:
        return args.auth_file
    return default_auth_file()


def validate_profile(profile: str):
    if not PROFILE_RE.match(profile):
        raise ValueError(f"auth profile 名称不合法：{profile}")


def load_auth_file(auth_file: Path) -> AuthFileModel | None:
    if not auth_file.exists():
        return None

    try:
        return AuthFileModel.model_validate(tomllib.loads(auth_file.read_text(encoding="utf-8")))
    except (ValidationError, ValueError):
        return None


def resolve_auth(args: Namespace) -> AuthInfo | None:
    if args.auth:
        parsed_auth = parse_auth_inline(args.auth)
        if parsed_auth is None:
            raise ValueError('auth 参数格式不正确哦，示例：--auth="SESSDATA=xxxxx; bili_jct=yyyyy"')
        return parsed_auth

    auth_file = resolve_auth_file(args)
    validate_profile(args.auth_profile)
    if not auth_file.exists():
        return None

    auth_file_model = load_auth_file(auth_file)
    if auth_file_model is None:
        raise ValueError(f"认证信息文件格式无效：{auth_file}")

    entry = auth_file_model.profiles.get(args.auth_profile)
    if entry is None or not entry.sessdata:
        return None
    return _auth_info_from_profile(entry)


def load_auth(auth_file: Path, profile: str) -> AuthInfo | None:
    validate_profile(profile)
    auth_file_model = load_auth_file(auth_file)
    if auth_file_model is None:
        return None

    entry = auth_file_model.profiles.get(profile)
    if entry is None:
        return None
    if not entry.sessdata:
        return None
    return _auth_info_from_profile(entry)


def _auth_info_from_profile(entry: AuthProfileModel) -> AuthInfo:
    auth_info = AuthInfo(SESSDATA=entry.sessdata, bili_jct=entry.bili_jct or None)
    if entry.cookies:
        auth_info["cookies"] = dict(entry.cookies)
    return auth_info


def save_auth(
    auth_file: Path,
    profile: str,
    sessdata: str,
    bili_jct: str | None,
    cookies: dict[str, str] | None = None,
):
    validate_profile(profile)

    profiles: dict[str, AuthProfileModel] = {}
    loaded = load_auth_file(auth_file)
    if loaded is not None:
        profiles = dict(loaded.profiles)

    original_entry = profiles.get(profile)
    entry_payload: dict[str, Any] = {}
    if original_entry is not None:
        entry_payload = original_entry.model_dump(exclude_none=True)

    entry_payload["sessdata"] = sessdata
    if bili_jct is not None:
        entry_payload["bili_jct"] = bili_jct
    else:
        entry_payload.pop("bili_jct", None)
    if cookies is not None:
        if cookies:
            entry_payload["cookies"] = dict(cookies)
        else:
            entry_payload.pop("cookies", None)
    entry_payload["updated_at"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    profiles[profile] = AuthProfileModel.model_validate(entry_payload)
    write_auth_file(auth_file, profiles)


def remove_auth(auth_file: Path, profile: str) -> bool:
    validate_profile(profile)
    loaded = load_auth_file(auth_file)
    if loaded is None:
        if auth_file.exists():
            raise ValueError(f"认证信息文件格式无效：{auth_file}")
        return False

    profiles = dict(loaded.profiles)
    if profile not in profiles:
        return False

    profiles.pop(profile)
    write_auth_file(auth_file, profiles)
    return True


def write_auth_file(auth_file: Path, profiles: dict[str, AuthProfileModel]) -> None:
    if not profiles:
        if auth_file.exists():
            auth_file.unlink()
        return

    auth_file.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for profile_name in sorted(profiles.keys()):
        profile_entry_dict = profiles[profile_name].model_dump(exclude_none=True)
        lines.append(f"[profiles.{profile_name}]")
        for key, value in profile_entry_dict.items():
            if key == "cookies":
                continue
            if isinstance(value, str):
                lines.append(f'{key} = "{escape_toml_basic_string(value)}"')
        cookies = profile_entry_dict.get("cookies")
        if isinstance(cookies, dict) and cookies:
            lines.append(f"[profiles.{profile_name}.cookies]")
            for name in sorted(cookies.keys()):
                value = cookies[name]
                if not isinstance(value, str) or not value:
                    continue
                lines.append(f'{format_toml_key(name)} = "{escape_toml_basic_string(value)}"')
        lines.append("")

    auth_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    if os.name != "nt":
        auth_file.chmod(0o600)


def save_sessdata(auth_file: Path, profile: str, sessdata: str):
    save_auth(auth_file, profile, sessdata, None)


def escape_toml_basic_string(raw: str) -> str:
    return raw.replace("\\", "\\\\").replace('"', '\\"')


_TOML_BARE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def format_toml_key(raw: str) -> str:
    if _TOML_BARE_KEY_RE.match(raw):
        return raw
    return f'"{escape_toml_basic_string(raw)}"'
