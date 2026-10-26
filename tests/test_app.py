import concurrent.futures
import datetime as dt
import unittest
import app
from tests_support import IntegrationTestsBase, Client

class IntegrationTests(IntegrationTestsBase):
    def test_public_catalog_filters_and_static_allowlist(self):
        code,data=self.guest.request('/api/catalog?category=Heritage&budget=2500');self.assertEqual(code,200)
        self.assertTrue(data['destinations']);self.assertTrue(all(d['category']=='Heritage' for d in data['destinations']))
        self.assertTrue(all(t['price_paise']<=250000 for t in data['tours']))
        self.assertEqual(self.guest.request('/api/catalog?budget=')[0],200)
        self.assertEqual(self.guest.request('/')[0],200)
        self.assertEqual(self.guest.request('/data/stms.db')[0],404)
        self.assertEqual(self.guest.request('/../app.py')[0],404)
    def test_registration_session_logout_and_expiry(self):
        d={'name':'Test Tourist','email':'new@example.com','password':'StrongPass123'}
        self.assertEqual(self.guest.request('/api/register','POST',d)[0],200)
        self.assertEqual(self.guest.request('/api/register','POST',d)[0],409)
        self.assertEqual(self.guest.request('/api/login','POST',d)[0],200)
        self.assertEqual(self.guest.request('/api/me')[1]['user']['role'],'tourist')
        self.assertTrue(all(c.has_nonstandard_attr('HttpOnly') for c in self.guest.cookies))
        self.guest.request('/api/logout','POST');self.assertIsNone(self.guest.request('/api/me')[1]['user'])
        with app.connect() as c: c.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.tourist.request('/api/bookings')[0],401)
    def test_security_validation_and_login_throttling(self):
        self.assertEqual(self.guest.request('/api/bookings')[0],401)
        self.assertEqual(self.tourist.request('/api/admin')[0],403)
        self.assertEqual(self.guide.request('/api/bookings','POST',{})[0],403)
        self.assertEqual(self.tourist.request('/api/logout','POST',headers={'Content-Type':'application/json'})[0],403)
        self.assertEqual(self.tourist.request('/api/logout','POST',headers={'Content-Type':'application/json','X-STMS-Request':'1','Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.book(seats=True)[0],400)
        self.assertEqual(self.book(seats=21)[0],400)
        for _ in range(10): self.assertEqual(self.guest.request('/api/login','POST',{'email':'x@example.com','password':'incorrect'})[0],401)
        self.assertEqual(self.guest.request('/api/login','POST',{'email':'x@example.com','password':'incorrect'})[0],429)
        self.assertEqual(self.guest.login('tourist@stms.local')[0],200)
    def test_booking_replay_totals_capacity_and_cancellation(self):
        code,b=self.book(seats=8);self.assertEqual(code,200)
        self.assertEqual(self.book(seats=8)[1]['id'],b['id'])
        self.assertEqual(self.book(seats=7)[0],409)
        self.assertEqual(self.book(seats=5,key='another-key')[0],409)
        item=self.tourist.request('/api/bookings')[1]['bookings'][0]
        self.assertEqual(item['total'],8*249900)
        self.assertEqual(self.tourist.request(f"/api/bookings/{b['id']}/status",'POST',{'status':'cancelled'})[0],200)
        self.assertEqual(self.book(seats=12,key='released-seats')[0],200)
        self.assertEqual(self.guide.request(f"/api/bookings/{b['id']}/status",'POST',{'status':'confirmed'})[0],409)
    def test_concurrent_reservations_cannot_overbook(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda key:self.book(seats=8,key=key)[0],['concurrent-a','concurrent-b']))
        self.assertEqual(sorted(results),[200,409])
        with app.connect() as c: self.assertEqual(c.execute('SELECT sum(seats) FROM bookings').fetchone()[0],8)
    def test_guide_lifecycle_and_verified_reviews(self):
        bid=self.book()[1]['id'];path=f'/api/bookings/{bid}/status'
        review={'destination_id':1,'rating':5,'comment':'Wonderful local experience.'}
        self.assertEqual(self.tourist.request('/api/reviews','POST',review)[0],403)
        self.assertEqual(self.guide.request(path,'POST',{'status':'completed'})[0],409)
        self.assertEqual(self.guide.request(path,'POST',{'status':'confirmed'})[0],200)
        self.assertEqual(self.guide.request(path,'POST',{'status':'completed'})[0],409)
        with app.connect() as c: c.execute('UPDATE tours SET date=? WHERE id=1',(app.today(),))
        self.assertEqual(self.tourist.request(path,'POST',{'status':'cancelled'})[0],409)
        self.assertEqual(self.guide.request(path,'POST',{'status':'completed'})[0],200)
        self.assertEqual(self.tourist.request('/api/reviews','POST',review)[0],200)
        review['rating']=4;self.assertEqual(self.tourist.request('/api/reviews','POST',review)[0],200)
        self.assertEqual(len(self.guest.request('/api/reviews')[1]['reviews']),1)
    def test_ownership_and_guide_assignment(self):
        with app.connect() as c:
            uid=c.execute("INSERT INTO users(name,email,password,role) VALUES('Other','other@example.com',?,'tourist')",(app.password_hash('Explore@12345'),)).lastrowid if not c.execute("SELECT id FROM users WHERE email='other@example.com'").fetchone() else c.execute("SELECT id FROM users WHERE email='other@example.com'").fetchone()[0]
            gid=c.execute("INSERT INTO users(name,email,password,role) VALUES('Other guide','otherguide@example.com',?,'guide')",(app.password_hash('Explore@12345'),)).lastrowid if not c.execute("SELECT id FROM users WHERE email='otherguide@example.com'").fetchone() else c.execute("SELECT id FROM users WHERE email='otherguide@example.com'").fetchone()[0]
        other=Client(self.base);other.login('other@example.com')
        bid=self.book()[1]['id'];self.assertEqual(other.request('/api/bookings')[1]['bookings'],[])
        self.assertEqual(other.request(f'/api/bookings/{bid}/status','POST',{'status':'cancelled'})[0],403)
        with app.connect() as c: c.execute('UPDATE tours SET guide_id=? WHERE id=1',(gid,))
        self.assertEqual(self.guide.request(f'/api/bookings/{bid}/status','POST',{'status':'confirmed'})[0],403)
        with app.connect() as c: c.execute('UPDATE tours SET guide_id=2 WHERE id=1')
        self.tourist.request('/api/itinerary','POST',{'destination_id':1,'date':app.today(),'title':'Explore','notes':'Private'})
        item=self.tourist.request('/api/itinerary')[1]['items'][0]
        self.assertEqual(other.request('/api/itinerary')[1]['items'],[])
        self.assertEqual(other.request('/api/itinerary/'+str(item['id']),'DELETE')[0],404)
        self.assertEqual(self.tourist.request('/api/itinerary/'+str(item['id']),'DELETE')[0],200)
    def test_support_admin_catalog_reports_and_audit(self):
        self.assertEqual(self.tourist.request('/api/tickets','POST',{'subject':'Booking question','message':'Please help.'})[0],200)
        ticket=self.admin.request('/api/tickets')[1]['tickets'][0]
        self.assertEqual(self.guide.request('/api/tickets')[1]['tickets'],[])
        self.assertEqual(self.admin.request(f"/api/tickets/{ticket['id']}/resolve",'POST',{'response':'Happy to help.'})[0],200)
        self.assertEqual(self.tourist.request('/api/tickets')[1]['tickets'][0]['status'],'resolved')
        d={'name':'Test destination','city':'Test City','category':'Nature','description':'A test destination.','active':1}
        code,result=self.admin.request('/api/admin/destinations','POST',d);self.assertEqual(code,200)
        dest=result['id'];d['id']=dest;d['active']=0
        self.assertEqual(self.admin.request('/api/admin/destinations','POST',d)[0],200)
        self.assertFalse(any(x['id']==dest for x in self.guest.request('/api/catalog')[1]['destinations']))
        tour={'destination_id':1,'guide_id':2,'date':(dt.date.today()+dt.timedelta(days=30)).isoformat(),'price_paise':150000,'capacity':6}
        self.assertEqual(self.admin.request('/api/admin/tours','POST',tour)[0],200)
        tour['guide_id']=1;self.assertEqual(self.admin.request('/api/admin/tours','POST',tour)[0],400)
        self.book();report=self.admin.request('/api/admin')[1]
        self.assertEqual(report['report']['reserved_value'],499800)
        self.assertTrue(report['audit'])
    def test_deactivation_and_invalid_dates(self):
        with app.connect() as c: c.execute('UPDATE destinations SET active=0 WHERE id=1')
        self.assertEqual(self.book()[0],400)
        self.assertEqual(self.tourist.request('/api/itinerary','POST',{'destination_id':2,'date':'not-a-date','title':'A','notes':''})[0],400)

if __name__=='__main__': unittest.main()
