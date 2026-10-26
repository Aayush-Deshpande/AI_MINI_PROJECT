import copy
import datetime as dt
import json
import os
from unittest.mock import patch
from tests_support import IntegrationTestsBase
import ai_planner


class AIPlannerTests(IntegrationTestsBase):
    def preferences(self):
        return {'destination_id':1,'start_date':(dt.date.today()+dt.timedelta(days=10)).isoformat(),'days':2,'budget':10000,'guests':2,'interests':'Heritage and relaxed walks'}

    def test_preview_plan_save_is_private_and_idempotent(self):
        with patch.dict(os.environ,{'NVIDIA_API_KEY':''}):
            self.assertFalse(self.guest.request('/api/ai/config')[1]['configured'])
            self.assertEqual(self.guest.request('/api/ai/plan','POST',self.preferences())[0],401)
            self.assertEqual(self.guide.request('/api/ai/plan','POST',self.preferences())[0],403)
            code,result=self.tourist.request('/api/ai/plan','POST',self.preferences())
        self.assertEqual(code,200);self.assertEqual(result['plan']['mode'],'preview')
        self.assertEqual(len(result['plan']['days']),2)
        path=f"/api/ai/plans/{result['id']}/save"
        self.assertEqual(self.tourist.request(path,'POST')[0],200)
        self.assertEqual(self.tourist.request(path,'POST')[0],200)
        self.assertEqual(len(self.tourist.request('/api/itinerary')[1]['items']),2)

    def test_nim_structured_result_and_invalid_output(self):
        d={'id':1,'name':'Pink City Heritage','city':'Jaipur','category':'Heritage','description':'Palaces and bazaars.'}
        raw=ai_planner.preview(self.preferences(),[d])
        raw['summary']='A personalised heritage itinerary.'
        with patch.dict(os.environ,{'NVIDIA_API_KEY':'test-placeholder-not-a-real-key'}),patch.object(ai_planner,'call_nim',return_value=json.dumps(raw)) as provider:
            code,result=self.tourist.request('/api/ai/plan','POST',self.preferences())
            self.assertEqual(code,200);self.assertEqual(result['plan']['mode'],'ai')
            context=json.loads(provider.call_args.args[0][1]['content'])
            self.assertEqual(context['catalog'][0]['id'],1)
            self.assertNotIn('email',json.dumps(context));self.assertNotIn('password',json.dumps(context))
            bad=copy.deepcopy(raw);bad['days'][0]['destination_id']=99999
            provider.return_value=json.dumps(bad)
            self.assertEqual(self.tourist.request('/api/ai/plan','POST',self.preferences())[0],502)
            provider.side_effect=ai_planner.PlannerError('Provider unavailable')
            self.assertEqual(self.tourist.request('/api/ai/plan','POST',self.preferences())[0],502)

    def test_ai_validation_rate_limit_and_plan_ownership(self):
        invalid=self.preferences();invalid['days']=8
        self.assertEqual(self.tourist.request('/api/ai/plan','POST',invalid)[0],400)
        with patch.dict(os.environ,{'NVIDIA_API_KEY':''}):
            first=self.tourist.request('/api/ai/plan','POST',self.preferences())[1]
            with self.db() as c:
                c.execute('UPDATE ai_plans SET user_id=2 WHERE id=?',(first['id'],))
            self.assertEqual(self.tourist.request(f"/api/ai/plans/{first['id']}/save",'POST')[0],404)
            for _ in range(9): self.assertEqual(self.tourist.request('/api/ai/plan','POST',self.preferences())[0],200)
            self.assertEqual(self.tourist.request('/api/ai/plan','POST',self.preferences())[0],429)
