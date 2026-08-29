from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SENSITIVE_QUERY_KEYS = {"token", "sig", "signature", "key", "auth", "jwt", "expires"}
_MODEL_EXTENSIONS = {".glb", ".gltf", ".bin", ".drc"}
_TEXTURE_EXTENSIONS = {".ktx2", ".basis", ".hdr", ".exr"}
_SHADER_EXTENSIONS = {".vert", ".frag", ".glsl", ".wgsl"}
_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
_FONT_EXTENSIONS = {".woff", ".woff2", ".ttf", ".otf"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg"}


@dataclass(frozen=True)
class AssetRecord:
    id: str
    type: str
    original_url: str
    local_path: str | None
    sha256: str | None
    bytes: int | None
    mime_type: str
    used_by: tuple[str, ...]
    access: str = "public-page-request"
    license: str = "unknown"
    status: str = "planned"
    reason: str | None = None
    decoder_dependencies: tuple[str, ...] = tuple()

    def as_json(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "type": self.type,
            "originalUrl": self.original_url,
            "localPath": self.local_path,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "mimeType": self.mime_type,
            "usedBy": list(self.used_by),
            "access": self.access,
            "license": self.license,
            "status": self.status,
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.decoder_dependencies:
            payload["decoderDependencies"] = list(self.decoder_dependencies)
        return payload


class AssetManifest:
    def __init__(
        self,
        staging_root: Path,
        max_file_bytes: int = 262_144_000,
        max_revision_bytes: int = 1_073_741_824,
    ):
        self.staging_root = staging_root.resolve()
        self.max_file_bytes = max_file_bytes
        self.max_revision_bytes = max_revision_bytes
        self.records: list[AssetRecord] = []

    @classmethod
    def load(
        cls,
        staging_root: Path,
        max_file_bytes: int = 262_144_000,
        max_revision_bytes: int = 1_073_741_824,
    ) -> "AssetManifest":
        manifest = cls(staging_root, max_file_bytes, max_revision_bytes)
        path = manifest.staging_root / "asset-manifest.json"
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            manifest.records = [_record_from_json(item) for item in raw.get("assets", [])]
        return manifest

    def plan(
        self,
        source_url: str,
        content_length: int | None,
        mime_type: str,
        used_by: list[str],
    ) -> AssetRecord:
        reason = None
        status = "planned"
        if content_length is not None and content_length > self.max_file_bytes:
            reason = "file-size-limit"
            status = "metadata-only"
        elif content_length is not None and self.downloaded_bytes + content_length > self.max_revision_bytes:
            reason = "revision-size-limit"
            status = "metadata-only"
        record = AssetRecord(
            id=_asset_id(source_url, None),
            type=classify_asset(source_url, mime_type),
            original_url=redact_url(source_url),
            local_path=None,
            sha256=None,
            bytes=content_length,
            mime_type=mime_type,
            used_by=tuple(used_by),
            status=status,
            reason=reason,
        )
        self.records.append(record)
        return record

    @property
    def downloaded_bytes(self) -> int:
        return sum(record.bytes or 0 for record in self.records if record.status == "downloaded")

    def add(self, record: AssetRecord) -> None:
        if record.status == "downloaded" and (record.bytes or 0) > self.max_file_bytes:
            raise ValueError("asset exceeds file-size limit")
        if record.status == "downloaded" and self.downloaded_bytes + (record.bytes or 0) > self.max_revision_bytes:
            raise ValueError("asset exceeds revision-size limit")
        self.records = [item for item in self.records if item.id != record.id]
        self.records.append(record)

    def write(self) -> Path:
        path = self.staging_root / "asset-manifest.json"
        payload = {"assets": [record.as_json() for record in sorted(self.records, key=lambda item: item.id)]}
        _atomic_write(path, _canonical_json(payload))
        return path


def classify_asset(source_url: str, mime_type: str) -> str:
    extension = Path(urlsplit(source_url).path).suffix.lower()
    if extension in _MODEL_EXTENSIONS or mime_type.startswith("model/"):
        return "model"
    if extension in _TEXTURE_EXTENSIONS:
        return "texture"
    if extension in _SHADER_EXTENSIONS:
        return "shader"
    if extension in _VIDEO_EXTENSIONS or mime_type.startswith("video/"):
        return "video"
    if extension in _FONT_EXTENSIONS or mime_type.startswith("font/"):
        return "font"
    if extension in _IMAGE_EXTENSIONS or mime_type.startswith("image/"):
        return "image"
    if extension in {".js", ".mjs", ".css", ".map"}:
        return "source-bundle"
    return "other"


def redact_url(source_url: str) -> str:
    parsed = urlsplit(source_url)
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        query.append((key, "REDACTED" if key.lower() in _SENSITIVE_QUERY_KEYS else value))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def record_download(
    staging_root: Path,
    source_url: str,
    relative_path: str,
    body: bytes,
    mime_type: str,
    used_by: list[str],
) -> AssetRecord:
    if len(body) > 262_144_000:
        raise ValueError("asset exceeds file-size limit")
    root = staging_root.resolve()
    destination = _safe_destination(root, relative_path)
    _atomic_write(destination, body)
    digest = hashlib.sha256(body).hexdigest()
    return AssetRecord(
        id=_asset_id(source_url, relative_path),
        type=classify_asset(source_url, mime_type),
        original_url=redact_url(source_url),
        local_path=PurePosixPath(relative_path).as_posix(),
        sha256=digest,
        bytes=len(body),
        mime_type=mime_type,
        used_by=tuple(used_by),
        status="downloaded",
    )


def record_file(
    staging_root: Path,
    source_url: str,
    relative_path: str,
    input_file: Path,
    mime_type: str,
    used_by: list[str],
    max_file_bytes: int = 262_144_000,
) -> AssetRecord:
    source = input_file.resolve()
    if not source.is_file() or source.is_symlink():
        raise ValueError("input asset must be a real file")
    if source.stat().st_size > max_file_bytes:
        raise ValueError("asset exceeds file-size limit")
    return record_download(
        staging_root, source_url, relative_path, source.read_bytes(), mime_type, used_by
    )


def publish_revision(staging_revision: Path, final_revision: Path, metadata: dict[str, object]) -> Path:
    staging = staging_revision.resolve()
    if not staging.is_dir() or staging.is_symlink():
        raise ValueError("staging revision must be a real directory")
    files = _hash_tree(staging)
    manifest = {**metadata, "files": files}
    manifest["manifestSha256"] = hashlib.sha256(_canonical_json(manifest)).hexdigest()

    final = final_revision.resolve()
    if final.exists():
        existing_path = final / "run-manifest.json"
        if not existing_path.is_file():
            raise FileExistsError(f"revision already exists without manifest: {final}")
        existing = json.loads(existing_path.read_text(encoding="utf-8"))
        if existing == manifest:
            return final
        raise FileExistsError(f"revision already exists with different content: {final}")

    _atomic_write(staging / "run-manifest.json", _canonical_json(manifest))
    _safe_mkdir_chain(final.parent)
    os.replace(staging, final)
    _fsync_directory(final.parent)
    return final


def _safe_destination(root: Path, relative_path: str) -> Path:
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("asset path must be a safe relative path")
    current = root
    for part in pure.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError("asset parent cannot be a symlink")
        current.mkdir(exist_ok=True)
        if not current.is_dir():
            raise ValueError("asset parent must be a directory")
    destination = current / pure.name
    if destination.is_symlink() or destination.exists() and not destination.is_file():
        raise ValueError("asset destination is unsafe")
    if root not in destination.resolve().parents:
        raise ValueError("asset path escapes staging root")
    return destination


def _safe_mkdir_chain(path: Path) -> None:
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    if current.is_symlink() or not current.is_dir():
        raise ValueError("revision parent is unsafe")
    for directory in reversed(missing):
        directory.mkdir()


def _hash_tree(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("revision tree cannot contain symlinks")
        if path.is_file() and path.name != "run-manifest.json":
            relative = path.relative_to(root).as_posix()
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _asset_id(source_url: str, relative_path: str | None) -> str:
    seed = f"{redact_url(source_url)}\n{relative_path or ''}".encode("utf-8")
    return "ASSET-" + hashlib.sha256(seed).hexdigest()[:12].upper()


def _record_from_json(raw: dict[str, object]) -> AssetRecord:
    return AssetRecord(
        id=str(raw["id"]),
        type=str(raw["type"]),
        original_url=str(raw["originalUrl"]),
        local_path=str(raw["localPath"]) if raw.get("localPath") is not None else None,
        sha256=str(raw["sha256"]) if raw.get("sha256") is not None else None,
        bytes=int(raw["bytes"]) if raw.get("bytes") is not None else None,
        mime_type=str(raw["mimeType"]),
        used_by=tuple(str(value) for value in raw.get("usedBy", [])),
        access=str(raw.get("access", "public-page-request")),
        license=str(raw.get("license", "unknown")),
        status=str(raw["status"]),
        reason=str(raw["reason"]) if raw.get("reason") is not None else None,
        decoder_dependencies=tuple(str(value) for value in raw.get("decoderDependencies", [])),
    )


def _canonical_json(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
