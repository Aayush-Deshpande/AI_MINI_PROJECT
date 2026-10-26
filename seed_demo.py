"""Add a complete fictional dataset once, without replacing existing records."""
import datetime as dt
import json
from pathlib import Path
import app

FIXTURE = Path(__file__).parent/'fixtures'/'demo.json'
DEMO_PASSWORD = 'Explore@12345'


def seed_demo():
    dataset=json.loads(FIXTURE.read_text(encoding='utf-8'))
    app.init_db(seed_base=False)
    with app.connect() as c:
        if c.dialect=='postgres': c.execute('SELECT pg_advisory_xact_lock(617028601)')
        else: c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM seed_runs WHERE name=?',(dataset['version'],)).fetchone():
            return {'applied':False,'version':dataset['version']}
        user_ids={}
        for person in dataset['users']:
            old=c.execute('SELECT id,role FROM users WHERE email=?',(person['email'],)).fetchone()
            if old and old['role']!=person['role']:
                raise ValueError(f"Demo email already has a different role: {person['email']}")
            user_ids[person['email']]=old['id'] if old else c.execute('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)',(person['name'],person['email'],app.password_hash(DEMO_PASSWORD),person['role'])).lastrowid
        tourists=[user_ids[p['email']] for p in dataset['users'] if p['role']=='tourist']
        guides=[user_ids[p['email']] for p in dataset['users'] if p['role']=='guide']
        admin=user_ids['admin@stms.local']
        anchor=dt.date.today()
        for i,d in enumerate(dataset['destinations']):
            old=c.execute('SELECT id FROM destinations WHERE name=? AND city=?',(d['name'],d['city'])).fetchone()
            dest=old['id'] if old else c.execute('INSERT INTO destinations(name,city,category,description) VALUES(?,?,?,?)',(d['name'],d['city'],d['category'],d['description'])).lastrowid
            departures=[]
            for offset in (8+i,22+i,36+i,50+i,-30+i):
                date=(anchor+dt.timedelta(days=offset)).isoformat()
                old=c.execute('SELECT id FROM tours WHERE destination_id=? AND date=? AND price_paise=? ORDER BY id LIMIT 1',(dest,date,d['price_paise'])).fetchone()
                tid=old['id'] if old else c.execute('INSERT INTO tours(destination_id,guide_id,date,price_paise,capacity) VALUES(?,?,?,?,?)',(dest,guides[i%len(guides)],date,d['price_paise'],12+(i%3)*4)).lastrowid
                departures.append(tid)
            statuses=('pending','confirmed','completed')
            for k,(tid,status) in enumerate(zip((departures[0],departures[1],departures[-1]),statuses)):
                owner=tourists[(i+k)%len(tourists)]
                # Ensure the primary demo account has a historical tour/review.
                if i==0 and status=='completed': owner=tourists[0]
                bid=c.execute('INSERT INTO bookings(user_id,tour_id,seats,unit_price,status,request_key) VALUES(?,?,?,?,?,?)',(owner,tid,1+(i%3),d['price_paise'],status,f'demo-v1-{i}-{status}')).lastrowid
                c.execute('INSERT INTO audit(actor,action,target) VALUES(?,?,?)',(admin,'demo.booking.'+status,bid))
                if status=='completed':
                    review=dataset['reviews'][i]
                    c.execute('INSERT INTO reviews(user_id,destination_id,rating,comment) VALUES(?,?,?,?) ON CONFLICT(user_id,destination_id) DO NOTHING',(owner,dest,review['rating'],review['comment']))
            if i%3==0:
                c.execute('INSERT INTO bookings(user_id,tour_id,seats,unit_price,status,request_key) VALUES(?,?,?,?,?,?)',(tourists[i%len(tourists)],departures[2],2,d['price_paise'],'cancelled',f'demo-v1-{i}-cancelled'))
            c.execute('INSERT INTO itinerary(user_id,destination_id,date,title,notes) VALUES(?,?,?,?,?)',(tourists[i%len(tourists)],dest,(anchor+dt.timedelta(days=8+i)).isoformat(),'Explore '+d['city'],'Fictional plan: meet the guide, explore local sights and leave time for a relaxed break.'))
        for i,t in enumerate(dataset['tickets']):
            c.execute('INSERT INTO tickets(user_id,subject,message,status,response) VALUES(?,?,?,?,?)',(tourists[i%len(tourists)],t['subject'],t['message'],'resolved' if t['response'] else 'open',t['response']))
        c.execute('INSERT INTO audit(actor,action,target) VALUES(?,?,?)',(admin,'demo.seeded',None))
        c.execute('INSERT INTO seed_runs(name) VALUES(?)',(dataset['version'],))
    return {'applied':True,'version':dataset['version']}


if __name__=='__main__': print(json.dumps(seed_demo(),indent=2))
