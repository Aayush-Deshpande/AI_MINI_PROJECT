"""Smart Tourist Management System. SQLite locally or PostgreSQL on Vercel."""
import datetime as dt
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import database
from config import load_env
import ai_planner

load_env()

ROOT = Path(__file__).parent
DB = os.environ.get('STMS_DB', str(ROOT / 'data' / 'stms.db'))
DATABASE_URL = os.environ.get('DATABASE_URL')

def connect():
    if os.environ.get('VERCEL') and not DATABASE_URL:
        raise RuntimeError('DATABASE_URL is required on Vercel. Local files are not persistent.')
    return database.connect(DB, DATABASE_URL)

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 310000).hex()

def today():
    return dt.date.today().isoformat()

def init_db(seed_base=True):
    if not DATABASE_URL: Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        if c.dialect == 'postgres': c.execute('SELECT pg_advisory_xact_lock(617028601)')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('tourist','guide','admin')),created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id),expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS destinations(id INTEGER PRIMARY KEY,name TEXT NOT NULL,city TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)));
        CREATE TABLE IF NOT EXISTS tours(id INTEGER PRIMARY KEY,destination_id INTEGER NOT NULL REFERENCES destinations(id),guide_id INTEGER NOT NULL REFERENCES users(id),date TEXT NOT NULL,price_paise INTEGER NOT NULL CHECK(price_paise>0),capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 200));
        CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),tour_id INTEGER NOT NULL REFERENCES tours(id),seats INTEGER NOT NULL CHECK(seats BETWEEN 1 AND 20),unit_price INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','confirmed','completed','cancelled')),request_key TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,request_key));
        CREATE TABLE IF NOT EXISTS itinerary(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),destination_id INTEGER NOT NULL REFERENCES destinations(id),date TEXT NOT NULL,title TEXT NOT NULL,notes TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),destination_id INTEGER NOT NULL REFERENCES destinations(id),rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),comment TEXT NOT NULL,UNIQUE(user_id,destination_id));
        CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),subject TEXT NOT NULL,message TEXT NOT NULL,status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved')),response TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor INTEGER REFERENCES users(id),action TEXT NOT NULL,target INTEGER,created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS seed_runs(name TEXT PRIMARY KEY,applied_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS login_limits(key TEXT PRIMARY KEY,attempts INTEGER NOT NULL,window_start REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS ai_plans(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),plan TEXT NOT NULL,saved INTEGER NOT NULL DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS booking_tour ON bookings(tour_id,status);
        CREATE INDEX IF NOT EXISTS booking_user ON bookings(user_id);
        ''')
        if seed_base and c.execute('SELECT count(*) FROM users').fetchone()[0] == 0:
            for name, email, role in [('Ayush','tourist@stms.local','tourist'),('Priya Sharma','guide@stms.local','guide'),('Administrator','admin@stms.local','admin')]:
                c.execute('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)',(name,email,password_hash('Explore@12345'),role))
            catalog = [
                ('Pink City Heritage','Jaipur','Heritage','Explore sandstone palaces, vibrant bazaars and the architectural stories of Rajasthan.',249900),
                ('Backwater Escape','Alleppey','Nature','Slow down beside palm-lined canals and discover the landscapes of Kerala.',349900),
                ('Himalayan Trails','Manali','Adventure','Discover mountain paths, cedar forests and dramatic valley views with a local guide.',299900),
                ('Old City Food Walk','Delhi','Food','Taste regional specialties and discover the streets and stories of Old Delhi.',149900),
                ('Coastal Discovery','Goa','Beach','Explore coastal villages, peaceful beaches and the distinctive heritage of Goa.',199900),
                ('Lakeside Stories','Udaipur','Heritage','Discover lakeside architecture, traditional craft and the history of the City of Lakes.',229900)]
            for idx,(name,city,category,description,price) in enumerate(catalog,1):
                c.execute('INSERT INTO destinations(name,city,category,description) VALUES(?,?,?,?)',(name,city,category,description))
                for days in (7,21):
                    date = (dt.date.today()+dt.timedelta(days=days+idx)).isoformat()
                    c.execute('INSERT INTO tours(destination_id,guide_id,date,price_paise,capacity) VALUES(?,2,?,?,12)',(idx,date,price))

class APIError(Exception):
    def __init__(self,message,status=400):
        self.message,self.status=message,status

def require(condition,message,status=400):
    if not condition: raise APIError(message,status)

def string(data,key,limit=200,minimum=1):
    v=data.get(key,'')
    require(isinstance(v,str),f'{key} must be text')
    v=v.strip()
    require(minimum<=len(v)<=limit,f'{key} must contain {minimum}–{limit} characters')
    return v

def integer(data,key,low=1,high=100000000):
    v=data.get(key)
    require(isinstance(v,int) and not isinstance(v,bool) and low<=v<=high,f'{key} must be an integer between {low} and {high}')
    return v

def date_value(data):
    v=string(data,'date',10)
    try: parsed=dt.date.fromisoformat(v)
    except ValueError: raise APIError('date must be YYYY-MM-DD')
    require(parsed.isoformat()==v,'date must be YYYY-MM-DD')
    return v

def audit(c,user,action,target):
    c.execute('INSERT INTO audit(actor,action,target) VALUES(?,?,?)',(user['id'],action,target))

class Handler(BaseHTTPRequestHandler):
    server_version='STMS'

    def log_message(self,fmt,*args):
        logging.info(fmt,*args)

    def send(self,status,body,content_type='application/json',cookie=None):
        raw=json.dumps(body).encode() if content_type=='application/json' else body
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self): self.handle_request('GET')
    def do_POST(self): self.handle_request('POST')
    def do_DELETE(self): self.handle_request('DELETE')

    def handle_request(self,method):
        parsed=urlparse(self.path)
        if not parsed.path.startswith('/api/'):
            files={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
            name=files.get(parsed.path)
            if method!='GET' or not name: return self.send(404,{'error':'Not found'})
            types={'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}
            return self.send(200,(ROOT/'static'/name).read_bytes(),types[name.split('.')[-1]])
        c=None
        try:
            c=connect()
            data={}
            if method!='GET':
                length=int(self.headers.get('Content-Length','0'))
                require(0<=length<=65536,'Request too large',413)
                raw=self.rfile.read(length)
                require(self.headers.get('X-STMS-Request')=='1','Missing request header',403)
                origin=self.headers.get('Origin')
                if origin:
                    o=urlparse(origin)
                    require(o.netloc==self.headers.get('Host') and o.scheme in ('http','https'),'Invalid origin',403)
                if length:
                    require(self.headers.get('Content-Type','').split(';')[0]=='application/json','Use application/json',415)
                    try: data=json.loads(raw)
                    except (ValueError,UnicodeError): raise APIError('Invalid JSON')
                    require(isinstance(data,dict),'JSON object required')
            cookie=SimpleCookie()
            try: cookie.load(self.headers.get('Cookie',''))
            except Exception: pass
            token=cookie['stms_session'].value if 'stms_session' in cookie else ''
            token_hash=hashlib.sha256(token.encode()).hexdigest()
            user=c.execute('SELECT u.id,u.name,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(token_hash,time.time())).fetchone()
            result,extra=self.route(c,method,parsed.path,parse_qs(parsed.query),data,user,token_hash)
            c.commit()
            self.send(200,result,cookie=extra)
        except APIError as e:
            if c: c.rollback()
            self.send(e.status,{'error':e.message})
        except (ValueError,TypeError):
            c.rollback(); self.send(400,{'error':'Invalid request value'})
        except sqlite3.IntegrityError:
            c.rollback(); self.send(409,{'error':'Conflicting or invalid record'})
        except Exception:
            if c: c.rollback()
            logging.exception('Request failed')
            self.send(503 if c is None else 500,{'error':'Database unavailable. Check deployment configuration.' if c is None else 'Internal server error'})
        finally:
            if c: c.close()

    def route(self,c,method,path,q,d,u,token_hash):
        def rows(sql,args=()): return [dict(r) for r in c.execute(sql,args)]
        def role(*roles):
            require(u is not None,'Please sign in',401)
            require(u['role'] in roles,'This action is not allowed for your role',403)
        def session_cookie(value,age):
            return f'stms_session={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}'+ ('; Secure' if os.environ.get('STMS_SECURE_COOKIE')=='1' or os.environ.get('VERCEL') else '')
        if path=='/api/health' and method=='GET':
            c.execute('SELECT count(*) FROM users').fetchone()
            return {'status':'ok','database':c.dialect},None
        if path=='/api/me' and method=='GET':
            return {'user':dict(u) if u else None,'demo':bool(c.execute('SELECT 1 FROM users WHERE email=?',('admin@stms.local',)).fetchone())},None
        if path=='/api/ai/config' and method=='GET': return ai_planner.configuration(),None
        if path=='/api/ai/plan' and method=='POST':
            role('tourist')
            preferences={'days':integer(d,'days',1,7),'budget':integer(d,'budget',1,1000000),'guests':integer(d,'guests',1,20),'interests':string(d,'interests',500)}
            preferences['start_date']=date_value({'date':d.get('start_date')})
            require(preferences['start_date']>=today(),'Choose today or a future start date')
            dest=integer(d,'destination_id',0)
            destinations=rows('SELECT id,name,city,category,description FROM destinations WHERE active=1'+(' AND id=?' if dest else ''),(dest,) if dest else ())
            require(bool(destinations),'No matching destinations are available')
            # Rate limits use the shared database, so cold starts cannot reset them.
            key='ai:'+str(u['id']); now=time.time()
            count=c.execute('''INSERT INTO login_limits(key,attempts,window_start) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET
                attempts=CASE WHEN login_limits.window_start<? THEN 1 ELSE login_limits.attempts+1 END,
                window_start=CASE WHEN login_limits.window_start<? THEN excluded.window_start ELSE login_limits.window_start END RETURNING attempts''',(key,now,now-3600,now-3600)).fetchone()[0]
            c.commit()
            require(count<=10,'You can create up to 10 plans per hour. Please try again later.',429)
            try: plan=ai_planner.generate(preferences,destinations)
            except ai_planner.PlannerError as exc: raise APIError(str(exc),502)
            cur=c.execute('INSERT INTO ai_plans(user_id,plan) VALUES(?,?)',(u['id'],json.dumps(plan)))
            return {'id':cur.lastrowid,'plan':plan},None
        if re.fullmatch(r'/api/ai/plans/\d+/save',path) and method=='POST':
            role('tourist'); pid=int(path.split('/')[4])
            c.execute('BEGIN IMMEDIATE')
            record=c.execute('SELECT * FROM ai_plans WHERE id=? AND user_id=?'+(' FOR UPDATE' if c.dialect=='postgres' else ''),(pid,u['id'])).fetchone()
            require(record is not None,'Plan not found',404)
            if record['saved']: return {'message':'This plan is already in your itinerary.'},None
            plan=json.loads(record['plan'])
            for day in plan['days']:
                require(c.execute('SELECT 1 FROM destinations WHERE id=? AND active=1',(day['destination_id'],)).fetchone(),'A destination is no longer available. Generate a new plan.',409)
                notes='\n'.join(k.title()+': '+day[k] for k in ('morning','afternoon','evening','notes'))[:2000]
                c.execute('INSERT INTO itinerary(user_id,destination_id,date,title,notes) VALUES(?,?,?,?,?)',(u['id'],day['destination_id'],day['date'],day['title'][:100],notes))
            c.execute('UPDATE ai_plans SET saved=1 WHERE id=?',(pid,))
            return {'message':'Plan added to your itinerary. Tour reservations are made separately.'},None
        if path=='/api/register' and method=='POST':
            name=string(d,'name',100); email=string(d,'email',254).lower(); password=string(d,'password',128,10)
            require(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email),'Enter a valid email')
            require(not c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone(),'Email is already registered',409)
            c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,'tourist')",(name,email,password_hash(password)))
            return {'message':'Account created. Sign in to continue.'},None
        if path=='/api/login' and method=='POST':
            email=string(d,'email',254).lower(); password=string(d,'password',128)
            # Persist the limiter across serverless workers. Use the account key
            # rather than trusting client-supplied forwarded IP headers.
            limit_key=hashlib.sha256(email.encode()).hexdigest(); now=time.time()
            attempt=c.execute('''INSERT INTO login_limits(key,attempts,window_start) VALUES(?,1,?)
                ON CONFLICT(key) DO UPDATE SET
                attempts=CASE WHEN login_limits.window_start<? THEN 1 ELSE login_limits.attempts+1 END,
                window_start=CASE WHEN login_limits.window_start<? THEN excluded.window_start ELSE login_limits.window_start END
                RETURNING attempts''',(limit_key,now,now-300,now-300)).fetchone()[0]
            c.commit()
            require(attempt<=10,'Too many attempts. Try again in five minutes.',429)
            account=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            stored=account['password'] if account else password_hash('dummy-password','00'*16)
            valid=hmac.compare_digest(password_hash(password,stored.split(':')[0]),stored)
            require(account is not None and valid,'Invalid email or password',401)
            c.execute('DELETE FROM login_limits WHERE key=? OR window_start<?',(limit_key,now-86400))
            token=secrets.token_hex(32)
            c.execute('DELETE FROM sessions WHERE expires<? OR token=?',(time.time(),token_hash))
            c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),account['id'],time.time()+43200))
            return {'message':'Signed in'},session_cookie(token,43200)
        if path=='/api/logout' and method=='POST':
            c.execute('DELETE FROM sessions WHERE token=?',(token_hash,))
            return {'message':'Signed out'},session_cookie('',0)
        if path=='/api/catalog' and method=='GET':
            destinations=rows('SELECT d.*, COALESCE((SELECT round(avg(rating),1) FROM reviews WHERE destination_id=d.id),0) rating FROM destinations d WHERE active=1')
            search=q.get('search',[''])[0].lower(); category=q.get('category',[''])[0]
            budget=int(q.get('budget',['0'])[0] or '0'); require(budget>=0,'Budget cannot be negative')
            tours=rows("SELECT t.*,u.name guide, t.capacity-COALESCE((SELECT sum(seats) FROM bookings b WHERE b.tour_id=t.id AND b.status!='cancelled'),0) available FROM tours t JOIN users u ON u.id=t.guide_id JOIN destinations d ON d.id=t.destination_id WHERE t.date>? AND d.active=1 ORDER BY t.date",(today(),))
            if budget: tours=[t for t in tours if t['price_paise']<=budget*100]
            destinations=[x for x in destinations if (not search or search in (x['name']+' '+x['city']+' '+x['description']).lower()) and (not category or x['category']==category) and (not budget or any(t['destination_id']==x['id'] for t in tours))]
            destinations.sort(key=lambda x:(-x['rating'],x['name']))
            return {'destinations':destinations,'tours':tours},None
        if path=='/api/bookings' and method=='GET':
            role('tourist','guide','admin')
            clause,args=('b.user_id=?',(u['id'],)) if u['role']=='tourist' else (('t.guide_id=?',(u['id'],)) if u['role']=='guide' else ('1=1',()))
            return {'bookings':rows('SELECT b.*,t.date,t.guide_id,d.name destination,us.name tourist,b.seats*b.unit_price total FROM bookings b JOIN tours t ON t.id=b.tour_id JOIN destinations d ON d.id=t.destination_id JOIN users us ON us.id=b.user_id WHERE '+clause+' ORDER BY b.id DESC',args)},None
        if path=='/api/bookings' and method=='POST':
            role('tourist'); tour_id=integer(d,'tour_id'); seats=integer(d,'seats',1,20); key=string(d,'request_key',100,8)
            c.execute('BEGIN IMMEDIATE')
            t=c.execute('SELECT t.*,d.active FROM tours t JOIN destinations d ON d.id=t.destination_id WHERE t.id=?'+c.lock_tour,(tour_id,)).fetchone()
            existing=c.execute('SELECT * FROM bookings WHERE user_id=? AND request_key=?',(u['id'],key)).fetchone()
            if existing:
                require(existing['tour_id']==tour_id and existing['seats']==seats,'Request key already used with different booking details',409)
                return {'id':existing['id'],'message':'Booking already received'},None
            require(t is not None,'Tour not found',404)
            require(t['active'] and t['date']>today(),'This tour is not available')
            used=c.execute("SELECT COALESCE(sum(seats),0) FROM bookings WHERE tour_id=? AND status!='cancelled'",(tour_id,)).fetchone()[0]
            require(used+seats<=t['capacity'],'Not enough seats available',409)
            cur=c.execute('INSERT INTO bookings(user_id,tour_id,seats,unit_price,request_key) VALUES(?,?,?,?,?)',(u['id'],tour_id,seats,t['price_paise'],key))
            audit(c,u,'booking.created',cur.lastrowid)
            return {'id':cur.lastrowid,'message':'Reservation requested. No payment has been collected.'},None
        if re.fullmatch(r'/api/bookings/\d+/status',path) and method=='POST':
            role('tourist','guide','admin'); bid=int(path.split('/')[3]); status=string(d,'status',20)
            c.execute('BEGIN IMMEDIATE')
            b=c.execute('SELECT b.*,t.date,t.guide_id FROM bookings b JOIN tours t ON t.id=b.tour_id WHERE b.id=?'+c.lock_booking,(bid,)).fetchone()
            require(b is not None,'Booking not found',404)
            if status=='cancelled':
                require((u['role']=='tourist' and b['user_id']==u['id']) or u['role']=='admin','Cannot cancel this booking',403)
                require(b['status'] in ('pending','confirmed') and b['date']>today(),'Booking cannot be cancelled',409)
            else:
                require(u['role']=='admin' or (u['role']=='guide' and b['guide_id']==u['id']),'Not assigned to this tour',403)
                require((b['status'],status) in (('pending','confirmed'),('confirmed','completed')),'Invalid status transition',409)
                if status=='completed': require(b['date']<=today(),'Cannot complete a tour before departure',409)
            c.execute('UPDATE bookings SET status=? WHERE id=?',(status,bid)); audit(c,u,'booking.'+status,bid)
            return {'message':'Booking updated'},None
        if path=='/api/itinerary':
            role('tourist')
            if method=='GET': return {'items':rows('SELECT i.*,d.name destination FROM itinerary i JOIN destinations d ON d.id=i.destination_id WHERE user_id=? ORDER BY date,id',(u['id'],))},None
            if method=='POST':
                dest=integer(d,'destination_id'); date=date_value(d); title=string(d,'title',100); notes=string(d,'notes',2000,0)
                require(c.execute('SELECT 1 FROM destinations WHERE id=? AND active=1',(dest,)).fetchone(),'Destination unavailable')
                c.execute('INSERT INTO itinerary(user_id,destination_id,date,title,notes) VALUES(?,?,?,?,?)',(u['id'],dest,date,title,notes))
                return {'message':'Itinerary item saved'},None
        if re.fullmatch(r'/api/itinerary/\d+',path) and method=='DELETE':
            role('tourist'); cur=c.execute('DELETE FROM itinerary WHERE id=? AND user_id=?',(int(path.split('/')[-1]),u['id']))
            require(cur.rowcount==1,'Item not found',404)
            return {'message':'Item deleted'},None
        if path=='/api/reviews':
            if method=='GET': return {'reviews':rows('SELECT r.*,u.name author,d.name destination FROM reviews r JOIN users u ON u.id=r.user_id JOIN destinations d ON d.id=r.destination_id ORDER BY r.id DESC')},None
            if method=='POST':
                role('tourist'); dest=integer(d,'destination_id'); rating=integer(d,'rating',1,5); comment=string(d,'comment',1000)
                require(c.execute("SELECT 1 FROM bookings b JOIN tours t ON t.id=b.tour_id WHERE b.user_id=? AND t.destination_id=? AND b.status='completed'",(u['id'],dest)).fetchone(),'Complete a booked tour here before reviewing',403)
                c.execute('INSERT INTO reviews(user_id,destination_id,rating,comment) VALUES(?,?,?,?) ON CONFLICT(user_id,destination_id) DO UPDATE SET rating=excluded.rating,comment=excluded.comment',(u['id'],dest,rating,comment))
                return {'message':'Review saved'},None
        if path=='/api/tickets':
            role('tourist','guide','admin')
            if method=='GET': return {'tickets':rows('SELECT t.*,u.name author FROM tickets t JOIN users u ON u.id=t.user_id'+('' if u['role']=='admin' else ' WHERE user_id=?')+' ORDER BY t.id DESC',() if u['role']=='admin' else (u['id'],))},None
            if method=='POST':
                c.execute('INSERT INTO tickets(user_id,subject,message) VALUES(?,?,?)',(u['id'],string(d,'subject',150),string(d,'message',3000)))
                return {'message':'Support request created'},None
        if re.fullmatch(r'/api/tickets/\d+/resolve',path) and method=='POST':
            role('admin'); tid=int(path.split('/')[3]); response=string(d,'response',3000)
            cur=c.execute("UPDATE tickets SET status='resolved',response=? WHERE id=?",(response,tid)); require(cur.rowcount==1,'Ticket not found',404)
            audit(c,u,'ticket.resolved',tid); return {'message':'Request resolved'},None
        if path=='/api/admin' and method=='GET':
            role('admin')
            report={k:c.execute(sql).fetchone()[0] for k,sql in {'users':'SELECT count(*) FROM users','destinations':'SELECT count(*) FROM destinations','bookings':'SELECT count(*) FROM bookings','reserved_value':"SELECT COALESCE(sum(seats*unit_price),0) FROM bookings WHERE status!='cancelled'"}.items()}
            report['by_status']=rows('SELECT status,count(*) count FROM bookings GROUP BY status')
            return {'report':report,'destinations':rows('SELECT * FROM destinations'),'guides':rows("SELECT id,name FROM users WHERE role='guide'"),'audit':rows('SELECT * FROM audit ORDER BY id DESC LIMIT 50')},None
        if path=='/api/admin/destinations' and method=='POST':
            role('admin'); name=string(d,'name',100); city=string(d,'city',100); category=string(d,'category',40); description=string(d,'description',2000); active=integer(d,'active',0,1)
            if d.get('id'):
                dest=integer(d,'id'); cur=c.execute('UPDATE destinations SET name=?,city=?,category=?,description=?,active=? WHERE id=?',(name,city,category,description,active,dest)); require(cur.rowcount==1,'Destination not found',404)
            else: dest=c.execute('INSERT INTO destinations(name,city,category,description,active) VALUES(?,?,?,?,?)',(name,city,category,description,active)).lastrowid
            audit(c,u,'destination.saved',dest); return {'message':'Destination saved','id':dest},None
        if path=='/api/admin/tours' and method=='POST':
            role('admin'); dest=integer(d,'destination_id'); guide=integer(d,'guide_id'); date=date_value(d); price=integer(d,'price_paise',1,100000000); capacity=integer(d,'capacity',1,200)
            require(date>today(),'Choose a future departure date')
            require(c.execute("SELECT 1 FROM users WHERE id=? AND role='guide'",(guide,)).fetchone(),'Invalid guide')
            require(c.execute('SELECT 1 FROM destinations WHERE id=? AND active=1',(dest,)).fetchone(),'Destination unavailable')
            cur=c.execute('INSERT INTO tours(destination_id,guide_id,date,price_paise,capacity) VALUES(?,?,?,?,?)',(dest,guide,date,price,capacity)); audit(c,u,'tour.created',cur.lastrowid)
            return {'message':'Tour scheduled'},None
        raise APIError('Endpoint not found',404)

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    init_db()
    host=os.environ.get('STMS_HOST','127.0.0.1'); port=int(os.environ.get('STMS_PORT','8000'))
    server=ThreadingHTTPServer((host,port),Handler)
    print(f'Smart Tourist Management System: http://{host}:{port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
