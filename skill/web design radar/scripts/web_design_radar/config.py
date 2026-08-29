from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path
    timezone: str
    daily_quota: int
    worker_slots: tuple[str, ...]
    stage_order: tuple[str, ...]
    coordinator_hour: int
    closeout_hour: int
    closeout_minute: int
    deadline_hour: int
    max_automatic_retries: int
    asset_max_file_bytes: int
    asset_max_revision_bytes: int
    desktop_viewport: tuple[int, int]
    mobile_viewport: tuple[int, int]
    browser_preference: str
    browser_fallback: str

    @property
    def db_path(self) -> Path:
        return self.root / "state" / "radar.sqlite3"

    @property
    def runs_path(self) -> Path:
        return self.root / "state" / "runs"

    @classmethod
    def from_env(cls) -> "Settings":
        skill_root = Path(__file__).resolve().parents[2]
        raw = json.loads((skill_root / "config" / "defaults.json").read_text(encoding="utf-8"))
        default_root = Path.home() / "Desktop" / "Web Design Radar"
        root = Path(os.environ.get("WEB_DESIGN_RADAR_ROOT", str(default_root))).expanduser().resolve()
        return cls(
            root=root,
            timezone=str(raw["timezone"]),
            daily_quota=int(raw["dailyQuota"]),
            worker_slots=tuple(str(value) for value in raw["workerSlots"]),
            stage_order=tuple(str(value) for value in raw["stageOrder"]),
            coordinator_hour=int(raw["coordinatorHour"]),
            closeout_hour=int(raw["closeoutHour"]),
            closeout_minute=int(raw["closeoutMinute"]),
            deadline_hour=int(raw["deadlineHour"]),
            max_automatic_retries=int(raw["maxAutomaticRetries"]),
            asset_max_file_bytes=int(raw["assetMaxFileBytes"]),
            asset_max_revision_bytes=int(raw["assetMaxRevisionBytes"]),
            desktop_viewport=tuple(int(value) for value in raw["desktopViewport"]),
            mobile_viewport=tuple(int(value) for value in raw["mobileViewport"]),
            browser_preference=str(raw["browserPreference"]),
            browser_fallback=str(raw["browserFallback"]),
        )
