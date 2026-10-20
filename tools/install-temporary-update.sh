#!/usr/bin/env bash
# Run as root on the pretix host; this updates the running container only.
set -Eeuo pipefail
cd /opt/pretix
container=pretix-pretix-1
commit=a44709304a1586eab5b8008f7c3161f7e91787ec
archive=/tmp/checkout-assistant-a447093.tar.gz
asset_sha=a55cf1d3d303c7124d702dea44df5edb5adb4ccf484001ec61f117570058500a
backup="/opt/pretix/checkout-assistant-backup-$(date -u +%Y%m%dT%H%M%SZ)"
trap 'echo "Update stopped. Backup, if already created: $backup" >&2' ERR

test "$(id -u)" = 0
docker inspect -f '{{.State.Running}}' "$container" | grep -qx true
curl -fsSL "https://codeload.github.com/ingofleckenstein/pretix-checkout-assistant/tar.gz/$commit" -o "$archive"
printf '%s  %s\n' '1fa87782a846b879b96a473928f2411bb1d4bb7a4b354be9e047852bb9104cf4' "$archive" | sha256sum -c -
docker exec -i "$container" python - <<'PY'
from pathlib import Path
import hashlib
import pretix
import pretix_checkout_assistant.automatic as automatic
assert pretix.__version__ == '2026.8.0', pretix.__version__
actual = hashlib.sha256(Path(automatic.__file__).read_bytes()).hexdigest()
assert actual == 'ed82004bc4eb2082c0ab0a74e7d5b3238e592a1c9453afc558c9a418af63ec20', actual
print('Existing pretix and plugin version verified.')
PY

mkdir "$backup"
docker exec -u 0 -i "$container" python - <<'PY'
import importlib.metadata
import tarfile
from pathlib import Path
import pretix_checkout_assistant
dist = importlib.metadata.distribution('pretix-checkout-assistant')
package = Path(pretix_checkout_assistant.__file__).parent
metadata = Path(dist._path)
assert package.parent == metadata.parent
with tarfile.open('/tmp/checkout-assistant-before-update.tar.gz', 'w:gz') as out:
    out.add(package, arcname=package.name)
    out.add(metadata, arcname=metadata.name)
print('Backed up installed package from:', package.parent)
PY
docker cp "$container:/tmp/checkout-assistant-before-update.tar.gz" "$backup/plugin.tar.gz"
docker cp "$container:/pretix/src/pretix/static.dist/staticfiles.json" "$backup/staticfiles.json"
docker cp "$archive" "$container:/tmp/checkout-assistant-update.tar.gz"
tar -xOf "$archive" pretix-checkout-assistant-a447093/tools/update-checkout-static.py > /tmp/update-checkout-static.py
docker exec -u 0 "$container" python -m pip install --force-reinstall --no-deps --no-build-isolation /tmp/checkout-assistant-update.tar.gz
docker exec -i -u 0 -e CHECKOUT_JS_SHA256="$asset_sha" "$container" python -m pretix shell < /tmp/update-checkout-static.py
docker exec -i -u 0 -e CHECKOUT_JS_SHA256="$asset_sha" -e CHECKOUT_STATIC_APPLY=1 "$container" python -m pretix shell < /tmp/update-checkout-static.py
docker exec "$container" python -m pretix shell -c 'from django.contrib.staticfiles.storage import staticfiles_storage; print(staticfiles_storage.url("pretix_checkout_assistant/automatic.js"))'
docker restart "$container"
docker exec "$container" python -m pretix check
curl -fsSI -H 'Host: tickets.spotstone.de' http://127.0.0.1:8345/static/pretix_checkout_assistant/automatic.93d4ae2253aa.js
printf '\nUpdate completed. Backup: %s\n' "$backup"
