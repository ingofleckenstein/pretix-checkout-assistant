"""Run through pretix shell; CHECKOUT_STATIC_APPLY=1 applies the guarded change."""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.files.base import ContentFile

name = "pretix_checkout_assistant/automatic.js"
root = Path(settings.STATIC_ROOT)
manifest = root / "staticfiles.json"
original = root / name
if not manifest.is_file() or not original.is_file():
    raise RuntimeError("Manifest or plugin JavaScript is missing; no changes made.")
expected_sha256 = "fda2a602fe72ab29c477a97e967c314b4e449edcaace11aefb9c003bc9bc9f7a"
if hashlib.sha256(original.read_bytes()).hexdigest() != expected_sha256:
    raise RuntimeError("Plugin JavaScript differs from the expected commit; no changes made.")
raw = manifest.read_bytes()
data = json.loads(raw)
if data.get("version") not in ("1.0", "1.1") or not isinstance(data.get("paths"), dict):
    raise RuntimeError("Unsupported manifest; no changes made.")
paths = data["paths"]
missing = [p for p in paths.values() if not (root / p).is_file()]
if missing:
    raise RuntimeError(f"Existing manifest references {len(missing)} missing files; no changes made.")
hashed = staticfiles_storage.hashed_name(name)
target = root / hashed
if paths.get(name) and paths[name] != hashed:
    raise RuntimeError("Manifest already contains a different plugin entry; no changes made.")
if target.exists() and target.read_bytes() != original.read_bytes():
    raise RuntimeError("Hashed target exists with different content; no changes made.")
print("Existing manifest entries:", len(paths))
print("Existing missing files:", len(missing))
print("Plugin hashed filename:", hashed)
if os.environ.get("CHECKOUT_STATIC_APPLY") != "1":
    print("Dry run only: no files changed.")
else:
    if paths.get(name) == hashed and target.is_file():
        print("Plugin entry is already present; no changes needed.")
    else:
        backup = root / "staticfiles.json.before-checkout-assistant"
        if backup.exists():
            raise RuntimeError("Backup already exists; inspect it before retrying.")
        if not target.exists():
            with original.open("rb") as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst)
        updated = dict(data)
        updated["paths"] = dict(paths)
        updated["paths"][name] = hashed
        updated["version"] = staticfiles_storage.manifest_version
        updated["hash"] = staticfiles_storage.file_hash(
            None, ContentFile(json.dumps(sorted(updated["paths"].items())).encode())
        )
        fd, temp_name = tempfile.mkstemp(prefix=".checkout-static-", dir=root)
        try:
            with os.fdopen(fd, "wb") as dest:
                dest.write(json.dumps(updated).encode())
            os.chmod(temp_name, manifest.stat().st_mode & 0o777)
            if manifest.read_bytes() != raw:
                raise RuntimeError("Manifest changed concurrently; not replaced.")
            with backup.open("xb") as dest:
                dest.write(raw)
            os.chmod(backup, manifest.stat().st_mode & 0o777)
            os.replace(temp_name, manifest)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        print("Added one manifest entry; backup:", backup)
