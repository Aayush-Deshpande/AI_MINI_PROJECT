"""Explicit database initialization and repeatable demonstration seeding."""
import argparse
import json
import os
import re
import app


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['init','seed-demo','check','create-guide'])
    parser.add_argument('--demo',action='store_true',help='Initialize with fictional data and publicly documented demo passwords.')
    parser.add_argument('--name',help='Name for create-guide')
    parser.add_argument('--email',help='Email for create-guide')
    args=parser.parse_args()
    if args.command=='create-guide':
        email=(args.email or '').strip().lower();name=(args.name or '').strip()
        password=os.environ.get('STMS_ACCOUNT_PASSWORD','')
        if not 1<=len(name)<=100 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not 14<=len(password)<=128:
            parser.error('Provide --name, --email and a private STMS_ACCOUNT_PASSWORD (14–128 characters).')
        with app.connect() as c:
            if c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone(): parser.error('Account already exists; no role or password was changed.')
            c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,'guide')",(name,email,app.password_hash(password)))
        print('Guide account created.');return
    if args.command=='check':
        with app.connect() as c:
            counts={table:c.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('users','destinations','tours','bookings','reviews','itinerary','tickets')}
            print(json.dumps({'database':c.dialect,'counts':counts},indent=2))
        return
    if args.command=='seed-demo' or args.demo:
        from seed_demo import seed_demo
        print(json.dumps(seed_demo(),indent=2))
        return
    email=os.environ.get('STMS_ADMIN_EMAIL','').strip().lower()
    password=os.environ.get('STMS_ADMIN_PASSWORD','')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not 14<=len(password)<=128 or password.startswith('replace-'):
        parser.error('Set STMS_ADMIN_EMAIL and a unique STMS_ADMIN_PASSWORD (14–128 characters), or use init --demo for a demonstration database.')
    app.init_db(seed_base=False)
    with app.connect() as c:
        if c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone():
            print('Account already exists; credentials and role were preserved.')
        else:
            c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,'admin')",(os.environ.get('STMS_ADMIN_NAME','Administrator'),email,app.password_hash(password)))
            print('Database initialized and administrator created.')


if __name__=='__main__': main()
