import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from leadintel.contact_enrichment import contact_plan, normalize_contacts, rank_contacts, save_contacts, request_contacts
from leadintel.store import Store, now


class ContactEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.store = Store(Path(self.temp.name) / 'contacts.sqlite')
        with self.store.db:
            run=self.store.db.execute("INSERT INTO research_runs(request_key,query,signal,source_ids,max_pages,max_depth,status,created_at) VALUES ('contacts-test','', 'award','[]',0,0,'completed',?)",(now(),)).lastrowid
            self.store.db.execute("INSERT INTO discovery_config VALUES (?,?,?,?,?)",(run,'Construction','Dallas','month','[]'))
            self.result_id=self.store.db.execute("INSERT INTO discovery_results(run_id,url,title,snippet,companies_json,signals_json,places_json,query) VALUES (?,?,?,?,?,?,?,?)",(run,'https://news.example/award','Atlas award','Atlas won.','[]','[]','[]','')).lastrowid
            classification={'company_name':'Atlas Builders','signal_type':'contract_award'}
            score={'passes':True}
            self.store.db.execute("INSERT INTO llm_classifications(result_id,status,model,prompt_version,classification_json,score,score_json,classified_at) VALUES (?,'completed','mock','v2',?,?,?,?)",(self.result_id,json.dumps(classification),90,json.dumps(score),now()))
            self.store.db.execute("INSERT INTO contractor_verifications(result_id,status,contractor_name,confidence,created_at,finished_at) VALUES (?,'completed','Atlas Builders','confirmed',?,?)",(self.result_id,now(),now()))

    def test_unresolved_project_does_not_target_the_developer(self):
        with self.store.db:
            self.store.db.execute("UPDATE contractor_verifications SET contractor_name=NULL, confidence='unresolved' WHERE result_id=?",(self.result_id,))
        with self.assertRaisesRegex(ValueError, 'Verify the general contractor'):
            contact_plan(self.store,self.result_id)

    def tearDown(self): self.store.close(); self.temp.cleanup()

    def test_plan_is_bounded_and_requires_verified_project_contractor(self):
        plan=contact_plan(self.store,self.result_id)
        self.assertEqual(plan['input']['totalResults'],5)
        self.assertEqual(plan['max_total_charge_usd'],0.10)
        self.assertEqual(plan['company'],'Atlas Builders')
        self.assertEqual(plan['input']['companyNameIncludes'], ['Atlas Builders'])
        self.assertIn('project manager', plan['input']['personTitleIncludes'])
        self.assertIn('principal', plan['input']['personTitleExcludes'])

    def test_location_is_not_silently_removed(self):
        with self.store.db:
            self.store.db.execute("UPDATE discovery_config SET location='Fort Worth'")
        self.assertNotIn('personLocationCityIncludes', contact_plan(self.store,self.result_id)['input'])

    def test_pipeline_output_format(self):
        contacts=normalize_contacts([{'fullName':'Test Person','title':'Project Manager',
            'linkedinUrl':'linkedin.com/in/test-person','email':'test@example.com',
            'personCity':'Dallas','personState':'Texas'}])
        self.assertEqual(contacts[0]['linkedin_url'], 'https://www.linkedin.com/in/test-person')
        self.assertEqual(contacts[0]['emails'], ['test@example.com'])
        self.assertEqual(contacts[0]['location'], 'Dallas, Texas')

    def test_actor_limit_is_not_reported_as_zero_results(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit):
                return json.dumps({'data':{'id':'run123','status':'SUCCEEDED',
                    'statusMessage':'free user run limit exceeded'}}).encode()
        with patch('leadintel.contact_enrichment.urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=Response()
            with self.assertRaisesRegex(ValueError, 'free-user run limit.*run123'):
                request_contacts({}, 'test-token')
            self.assertEqual(opener.return_value.open.call_count, 1)

    def test_actor_status_poll_then_dataset(self):
        class Response:
            def __init__(self, value): self.value=value
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return json.dumps(self.value).encode()
        with patch('leadintel.contact_enrichment.urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=[Response({'data':{'id':'run123','status':'RUNNING'}}),
                Response({'data':{'id':'run123','status':'SUCCEEDED','defaultDatasetId':'data123'}}),
                Response([{'fullName':'Test Person'}])]
            self.assertEqual(request_contacts({}, 'test-token'), [{'fullName':'Test Person'}])

    def test_bad_records_are_not_reported_as_no_matches(self):
        with self.assertRaisesRegex(ValueError, 'not a zero-match'):
            normalize_contacts([{'error':'Actor account limit reached'}])
        self.assertEqual(normalize_contacts([]), [])

    def test_profile_verification_does_not_verify_email(self):
        contacts=normalize_contacts([{'firstName':'Ava','lastName':'Stone',
            'linkedinUrl':'https://www.linkedin.com/in/ava',
            'location':'Dallas, Texas','verified':True,'emails':['ava@example.com']}])
        self.assertEqual(contacts[0]['location'], 'Dallas, Texas')
        self.assertFalse(contacts[0]['provider_verified'])

    def test_normalize_rank_and_save_contacts(self):
        contacts=normalize_contacts([{'firstName':'Ava','lastName':'Stone','linkedinUrl':'https://www.linkedin.com/in/ava','headline':'Operations Director','verified':True,'emails':['ava@atlas.example']}])
        def transport(body,key):
            return {'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'contacts':[{'source_index':0,'relevance':91,'reason':'Leads operations.','suitable':True}]})}]}]}
        ranked=rank_contacts(contacts,'Atlas Builders','test-key',transport)
        with self.store.db:
            run=self.store.db.execute("INSERT INTO contact_runs(result_id,company,status,created_at) VALUES (?,?,'completed',?)",(self.result_id,'Atlas Builders',now())).lastrowid
        self.assertEqual(save_contacts(self.store,run,ranked),1)
        self.assertEqual(self.store.rows('SELECT relevance FROM lead_contacts')[0]['relevance'],91)

    def test_review_excludes_unsuitable_roles(self):
        contacts=normalize_contacts([
            {'fullName':'Adrian Example','title':'Project Manager','linkedinUrl':'linkedin.com/in/adrian-example'},
            {'fullName':'Jordan Example','title':'CEO','linkedinUrl':'linkedin.com/in/jordan-example'}])
        def transport(body,key):
            self.assertIn('reported_company',body['input'])
            return {'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'contacts':[
                {'source_index':0,'relevance':90,'reason':'Project manager','suitable':True},
                {'source_index':1,'relevance':10,'reason':'CEO is not an operational role','suitable':False}]})}]}]}
        reviewed=rank_contacts(contacts,'Atlas Builders','test-key',transport)
        self.assertEqual([c['name'] for c in reviewed],['Adrian Example'])

    def test_normalize_accepts_current_actor_output_shape(self):
        contacts=normalize_contacts([{'name':'Jake Haigh','profileUrl':'https://www.linkedin.com/in/jake-haigh',
          'currentPosition':{'title':'Project Manager'},'headline':'Ignored when a title is supplied'}])
        self.assertEqual(contacts[0]['name'],'Jake Haigh')
        self.assertEqual(contacts[0]['title'],'Project Manager')


if __name__ == '__main__': unittest.main()
