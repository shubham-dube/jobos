from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path


def default_home() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "JobOS"
    return Path.home() / ".jobos"


@dataclass
class RunnerConfig:
    api_url: str = "http://localhost:8000"
    token: str = ""
    name: str = platform.node() or "runner"
    profile_dir: str = ""  # Chrome user-data-dir dedicated to JobOS
    browser_channel: str = "chrome"  # installed Google Chrome; "" = bundled Chromium
    executable_path: str = ""  # explicit browser binary (tests / custom installs)
    headless: bool = False
    max_sessions: int = 2  # parallel tabs (applications) at once
    slow_typing: bool = True  # human-like typing
    downloads_dir: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def home(self) -> Path:
        return default_home()

    def resolved_profile_dir(self) -> Path:
        return Path(self.profile_dir) if self.profile_dir else self.home / "chrome-profile"

    def resolved_downloads_dir(self) -> Path:
        return Path(self.downloads_dir) if self.downloads_dir else self.home / "files"


def config_path() -> Path:
    return default_home() / "runner.json"


def load_config() -> RunnerConfig:
    path = config_path()
    cfg = RunnerConfig()
    if path.exists():
        data = json.loads(path.read_text())
        cfg = RunnerConfig(**{k: v for k, v in data.items() if k in RunnerConfig.__dataclass_fields__})
    # env overrides (useful for tests and services)
    for key in ("api_url", "token", "profile_dir", "browser_channel", "executable_path"):
        env = os.environ.get(f"JOBOS_RUNNER_{key.upper()}")
        if env is not None:
            setattr(cfg, key, env)
    if os.environ.get("JOBOS_RUNNER_HEADLESS"):
        cfg.headless = os.environ["JOBOS_RUNNER_HEADLESS"] == "1"
    return cfg


def save_config(cfg: RunnerConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path
