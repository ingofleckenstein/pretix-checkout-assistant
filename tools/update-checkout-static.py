"""Safely update only this plugin's hashed asset; default is a dry run."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.files.base import ContentFile
import pretix_checkout_assistant

name = 'pretix_checkout_assistant/automatic.js'
root = Path(settings.STATIC_ROOT)
manifest = root / 'staticfiles.json'
source = Path(pretix_checkout_assistant.__file__).parent / 'static/pretix_checkout_assistant/automatic.js'
raw = manifest.read_bytes()
data = json.loads(raw)
if data.get('version') not in ('1.0', '1.1') or not isinstance(data.get('paths'), dict):
    raise RuntimeError('Unsupported staticfiles manifest')
paths = data['paths']
missing = [p for p in paths.values() if not (root / p).is_file()]
if missing:
    raise RuntimeError(f'Manifest already contains {len(missing)} missing files')
content = source.read_bytes()
expected = os.environ.get('CHECKOUT_JS_SHA256', '')
if not expected or hashlib.sha256(content).hexdigest() != expected:
    raise RuntimeError('Installed JavaScript does not match the expected SHA256')
hashed = staticfiles_storage.hashed_name(name, content=ContentFile(content))
target = root / hashed
if target.exists() and target.read_bytes() != content:
    raise RuntimeError('Hashed asset already exists with different contents')
print('Previous entry:', paths.get(name, '(none)'))
print('New entry:', hashed)
print('Existing missing files:', len(missing))
if os.environ.get('CHECKOUT_STATIC_APPLY') != '1':
    print('Dry run only; no files changed.')
else:
    if paths.get(name) == hashed and target.is_file():
        print('Already up to date.')
    else:
        if not target.exists():
            with target.open('xb') as f:
                f.write(content)
        updated = dict(data)
        updated['paths'] = dict(paths, **{name: hashed})
        updated['version'] = staticfiles_storage.manifest_version
        updated['hash'] = staticfiles_storage.file_hash(
            None, ContentFile(json.dumps(sorted(updated['paths'].items())).encode()))
        fd, temp = tempfile.mkstemp(prefix='.checkout-manifest-', dir=root)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(json.dumps(updated).encode())
            os.chmod(temp, manifest.stat().st_mode & 0o777)
            if manifest.read_bytes() != raw:
                raise RuntimeError('Manifest changed concurrently; not replaced')
            fd, backup = tempfile.mkstemp(prefix='staticfiles.json.before-checkout-update-', dir=root)
            with os.fdopen(fd, 'wb') as f:
                f.write(raw)
            os.chmod(backup, manifest.stat().st_mode & 0o777)
            os.replace(temp, manifest)
            print('Updated manifest; backup:', backup)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
