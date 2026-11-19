"""Connect this copy of the simulator to the running local store."""
from pathlib import Path
import json
import subprocess
import sys
from urllib.request import urlopen
from urllib.error import URLError
from urllib.parse import urlsplit
from tempfile import NamedTemporaryFile

root=Path(__file__).resolve().parent
path=root/'connection.json'
cfg=json.loads(path.read_text(encoding='utf-8-sig'))
target=cfg.get('kiranaconnect_url','http://127.0.0.1:8000').rstrip('/')
try:
    with urlopen(target+'/openapi.json',timeout=4) as resp:
        routes=json.load(resp)['paths']
    if not {'/api/customer/message','/api/customer/thread','/api/chat','/api/customer/image'} <= routes.keys():
        raise ValueError('The running store needs the updated messaging API.')
except (URLError,KeyError,ValueError,OSError) as exc:
    print('Could not connect to KiranaConnect at '+target+'. Start Start-Windows.ps1 in the KiranaConnect project, then run this launcher again.',exc)
    sys.exit(1)
cfg.update(mode='connected',kiranaconnect_url=target)
with NamedTemporaryFile('w',dir=root,encoding='utf-8',delete=False) as f:
    json.dump(cfg,f,indent=2);tmp=Path(f.name)
tmp.replace(path)
print('Store connection checked. Opening the connected WhatsApp simulator.',flush=True)
sys.exit(subprocess.call([sys.executable,str(root/'server.py'),'--open'],cwd=root))
