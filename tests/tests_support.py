import concurrent.futures
import datetime as dt
import http.cookiejar
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

class Client:
    def __init__(self,base):
        self.base=base
        self.cookies=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
    def request(self,path,method='GET',data=None,headers=None):
        h={'Content-Type':'application/json','X-STMS-Request':'1'}
        if headers is not None: h=headers
        req=urllib.request.Request(self.base+path,data=json.dumps(data or {}).encode() if method!='GET' else None,headers=h,method=method)
        try: response=self.opener.open(req)
        except urllib.error.HTTPError as e: response=e
        with response:
            raw=response.read()
            return response.status,json.loads(raw) if 'application/json' in response.headers.get('Content-Type','') else raw
    def login(self,email):
        return self.request('/api/login','POST',{'email':email,'password':'Explore@12345'})

class IntegrationTestsBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.original_url=app.DATABASE_URL
        cls.test_url=os.environ.get('STMS_TEST_DATABASE_URL')
        if cls.test_url:
            import psycopg
            from psycopg.conninfo import make_conninfo
            import secrets
            cls.schema='stms_test_'+secrets.token_hex(6)
            with psycopg.connect(cls.test_url,autocommit=True) as c:
                c.execute('CREATE SCHEMA '+cls.schema)
            app.DATABASE_URL=make_conninfo(cls.test_url,options='-c search_path='+cls.schema)
        else:
            app.DATABASE_URL=None
        app.DB=str(Path(cls.tmp.name)/'test.db')
        app.init_db()
        cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
        app.DATABASE_URL=cls.original_url
        if cls.test_url:
            import psycopg
            with psycopg.connect(cls.test_url,autocommit=True) as c: c.execute('DROP SCHEMA '+cls.schema+' CASCADE')
    def setUp(self):
        with app.connect() as c:
            for table in ('audit','reviews','itinerary','tickets','bookings','sessions','login_limits','ai_plans'): c.execute('DELETE FROM '+table)
            c.execute('UPDATE destinations SET active=1')
            c.execute('UPDATE tours SET date=?,capacity=12',((dt.date.today()+dt.timedelta(days=10)).isoformat(),))
        self.tourist=Client(self.base);self.guide=Client(self.base);self.admin=Client(self.base);self.guest=Client(self.base)
        for client,email in ((self.tourist,'tourist@stms.local'),(self.guide,'guide@stms.local'),(self.admin,'admin@stms.local')):
            self.assertEqual(client.login(email)[0],200)
    db=staticmethod(app.connect)
    def book(self,client=None,seats=2,key='request-key-0001',tour=1):
        return (client or self.tourist).request('/api/bookings','POST',{'tour_id':tour,'seats':seats,'request_key':key})
