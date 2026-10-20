#!/usr/bin/env bash
# Temporary update of the existing pretix container. Run as root.
set -Eeuo pipefail
cd /opt/pretix
container=pretix-pretix-1
commit=bf9f7b2ab47cc9709b4f9186cf803a381dcb58ee
archive=/tmp/checkout-assistant-bf9f7b2.tar.gz
backup="/opt/pretix/checkout-assistant-backup-$(date -u +%Y%m%dT%H%M%SZ)"
trap 'echo "UPDATE STOPPED. Backup, if created: $backup" >&2' ERR

test "$(id -u)" = 0
test "$(docker inspect -f '{{.State.Running}}' "$container")" = true
curl -fsSL "https://codeload.github.com/ingofleckenstein/pretix-checkout-assistant/tar.gz/$commit" -o "$archive"
printf '%s  %s\n' 06f1f808acaa556bee9705bd83c3497f15032b576015ccb4b414c4dd78e64093 "$archive" | sha256sum -c -

docker exec -i "$container" python - <<'PY'
import hashlib
from pathlib import Path
from importlib.metadata import version
import pretix
import pretix_checkout_assistant.automatic as automatic
import pretix_checkout_assistant.invoice_notice as notice
assert pretix.__version__ == '2026.8.0', pretix.__version__
assert version('pretix-checkout-assistant') == '0.0.2.dev0'
assert hashlib.sha256(Path(automatic.__file__).read_bytes()).hexdigest() == '384cec581a63fc840c35ed30a88cae5c6e4bbc93de0eec6b7d5ed4b8cbec8dc2'
assert hashlib.sha256(Path(notice.__file__).read_bytes()).hexdigest() == 'd8043f8d997b5df0079142d9cdd61af2e0e7ccc5a3ee256c3ac17229d762a228'
print('Installed versions verified.')
PY

mkdir "$backup"
docker exec -i -u 0 "$container" python - <<'PY'
import importlib.metadata
import tarfile
from pathlib import Path
import pretix_checkout_assistant
package = Path(pretix_checkout_assistant.__file__).parent
metadata = Path(importlib.metadata.distribution('pretix-checkout-assistant')._path)
assert package.parent == metadata.parent
with tarfile.open('/tmp/checkout-assistant-before-bf9f7b2.tar.gz', 'w:gz') as out:
    out.add(package, arcname=package.name)
    out.add(metadata, arcname=metadata.name)
PY
docker cp "$container:/tmp/checkout-assistant-before-bf9f7b2.tar.gz" "$backup/plugin.tar.gz"
docker cp "$container:/pretix/src/pretix/static.dist/staticfiles.json" "$backup/staticfiles.json"
docker cp "$archive" "$container:/tmp/checkout-assistant-bf9f7b2.tar.gz"
docker exec -u 0 "$container" python -m pip install --force-reinstall --no-deps --no-build-isolation /tmp/checkout-assistant-bf9f7b2.tar.gz

docker exec -i "$container" python - <<'PY'
import hashlib
from pathlib import Path
import pretix_checkout_assistant.invoice_notice as notice
import pretix_checkout_assistant.fee_limits as fees
assert hashlib.sha256(Path(notice.__file__).read_bytes()).hexdigest() == '0840673b5f42e97b6f849ac34c69eefab687f8d75ba9fc10917df0a14f08751e'
assert hashlib.sha256(Path(fees.__file__).read_bytes()).hexdigest() == '72b3d6955c1809114ba43b6c4d6344be7be28531b1e1f7fa2fdc61dc117fbfb1'
print('Updated files verified.')
PY
docker exec "$container" python -m pretix check
docker restart "$container"

ready=0
for attempt in $(seq 1 30); do
  if curl -fsS -o /dev/null -H 'Host: tickets.spotstone.de' http://127.0.0.1:8345/; then
    ready=1
    break
  fi
  sleep 2
done
test "$ready" = 1
docker exec "$container" python -m pretix check
docker exec "$container" python -m pretix shell -c 'from django.contrib.staticfiles.storage import staticfiles_storage; print("Plugin static URL:", staticfiles_storage.url("pretix_checkout_assistant/automatic.js"))'
printf '\nUpdate completed. Backup: %s\n' "$backup"


