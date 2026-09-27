"""Content-addressed, validated cache for immutable per-file parser facts only."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path


ANALYZER_VERSION = "static-facts-v1"
DISABLED_MARKER = "static-facts-disabled.json"



def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FactsCache:
    """Expose per-file hit/miss provenance through ``events`` after each scan."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.events: list[dict[str, str | None]] = []
    @property
    def disabled_reason(self) -> str | None:
        """Fail closed even when the owner-controlled marker is malformed."""
        marker = self.directory / DISABLED_MARKER
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, UnicodeDecodeError):
            return "invalid_disabled_marker"
        if (not isinstance(data, dict) or data.get("version") != 1 or
                data.get("reason") != "replay_mismatch"):
            return "invalid_disabled_marker"
        return "replay_mismatch"

    def disable(self) -> None:
        """Persist replay mismatch without touching existing cache entries."""
        self.directory.mkdir(parents=True, exist_ok=True)
        marker = self.directory / DISABLED_MARKER
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.directory,
                                         prefix="static-facts-disabled.", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"version": 1, "reason": "replay_mismatch"}, stream)
        try:
            temporary.replace(marker)
        finally:
            temporary.unlink(missing_ok=True)


    def facts(self, path: str, source: bytes, source_root: str, compute):
        source_hash = digest(source)
        identity = {"source_sha256": source_hash, "path": path,
                    "source_root": source_root, "parser": sys.version.split()[0],
                    "analyzer": ANALYZER_VERSION}
        key = digest(json.dumps(identity, sort_keys=True).encode("utf-8"))
        target = self.directory / f"{key}.json"
        try:
            envelope = json.loads(target.read_bytes())
            payload = envelope["payload"]
            payload_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=True,
                                       separators=(",", ":")).encode("utf-8")
            if (envelope["identity"] != identity or
                    envelope["payload_sha256"] != digest(payload_bytes) or
                    not isinstance(payload, dict) or "blob_oid" in payload or
                    payload.get("path") != path or payload.get("source_sha256") != source_hash):
                raise ValueError("cache entry mismatch")
            origin, reason = "hit", None
        except (OSError, ValueError, TypeError, KeyError, UnicodeDecodeError) as error:
            reason = "missing" if isinstance(error, FileNotFoundError) else "invalid"
            payload = compute()
            payload.pop("blob_oid")
            payload_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=True,
                                       separators=(",", ":")).encode("utf-8")
            envelope = {"identity": identity, "payload": payload,
                        "payload_sha256": digest(payload_bytes)}
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.directory,
                                             prefix=f"{key}.", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(envelope, stream, sort_keys=True)
            try:
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            origin = "miss"
        self.events.append({"path": path, "origin": origin, "source_sha256": source_hash,
                            "cache_key": key, "invalidation_reason": reason,
                            "artifact_sha256": digest(payload_bytes)})
        return payload
