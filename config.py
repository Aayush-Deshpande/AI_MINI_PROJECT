"""Read an optional local .env; deployed environment variables take precedence."""
import os
from pathlib import Path


def load_env():
    path=Path(__file__).parent/'.env'
    if os.environ.get('VERCEL') or not path.is_file(): return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        key,value=line.split('=',1)
        key,value=key.strip(),value.strip()
        if len(value)>1 and value[0]==value[-1] and value[0] in ('"',"'"): value=value[1:-1]
        if key.replace('_','').isalnum(): os.environ.setdefault(key,value)
