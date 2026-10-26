"""Create a consistent SQLite backup without overwriting an existing file."""
import argparse
from pathlib import Path
import sqlite3
import app

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    if app.DATABASE_URL: parser.error('For PostgreSQL, use provider backups or pg_dump; this utility is for SQLite only.')
    source=Path(app.DB).resolve()
    if not source.is_file(): parser.error('Database does not exist. Start the app first.')
    args.destination.parent.mkdir(parents=True,exist_ok=True)
    try:
        with args.destination.open('xb'): pass
    except FileExistsError: parser.error('Backup already exists; choose another destination.')
    src=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    dest=sqlite3.connect(args.destination)
    try: src.backup(dest)
    finally: dest.close();src.close()
    print(f'Backup created: {args.destination.resolve()}')

if __name__=='__main__': main()
