import datetime as dt
from pathlib import Path
import tempfile
import unittest
import app
from seed_demo import seed_demo


class DemoSeedTests(unittest.TestCase):
    def test_full_dataset_is_repeatable_and_preserves_user_data(self):
        old_db,old_url=app.DB,app.DATABASE_URL
        with tempfile.TemporaryDirectory() as tmp:
            try:
                app.DB=str(Path(tmp)/'seed.db');app.DATABASE_URL=None
                app.init_db()
                with app.connect() as c:
                    c.execute("INSERT INTO itinerary(user_id,destination_id,date,title,notes) VALUES(1,1,?,'My own plan','Keep me')",(app.today(),))
                self.assertTrue(seed_demo()['applied'])
                with app.connect() as c:
                    expected={'users':11,'destinations':12,'tours':60,'bookings':40,'reviews':12,'itinerary':13,'tickets':8}
                    counts={t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in expected}
                    self.assertEqual(counts,expected)
                    self.assertEqual(c.execute("SELECT count(*) FROM tours WHERE date>?",(app.today(),)).fetchone()[0],48)
                    self.assertEqual(c.execute("SELECT count(*) FROM reviews r WHERE NOT EXISTS(SELECT 1 FROM bookings b JOIN tours t ON t.id=b.tour_id WHERE b.user_id=r.user_id AND t.destination_id=r.destination_id AND b.status='completed')").fetchone()[0],0)
                    self.assertEqual(c.execute("SELECT count(*) FROM tours t WHERE (SELECT COALESCE(sum(seats),0) FROM bookings b WHERE b.tour_id=t.id AND b.status!='cancelled')>t.capacity").fetchone()[0],0)
                self.assertFalse(seed_demo()['applied'])
                with app.connect() as c:
                    self.assertEqual(c.execute('SELECT count(*) FROM itinerary').fetchone()[0],13)
                    self.assertEqual(c.execute("SELECT notes FROM itinerary WHERE title='My own plan'").fetchone()[0],'Keep me')
            finally: app.DB,app.DATABASE_URL=old_db,old_url


if __name__=='__main__': unittest.main()
