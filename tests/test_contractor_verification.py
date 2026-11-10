import json
import re
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from leadintel.contractor_verification import eligible, reuse_completed, run, search_plan
from leadintel.research import ResearchController
from leadintel.store import Store, now
from leadintel.web import handler


class ContractorVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/'verify.sqlite'
        self.store=Store(self.path)
        with self.store.db:
            run_id=self.store.db.execute("""INSERT INTO research_runs
              (request_key,query,signal,source_ids,max_pages,max_depth,status,created_at)
              VALUES ('verify-run','', 'mobilization','[]',0,0,'completed',?)""",(now(),)).lastrowid
            self.store.db.execute("INSERT INTO discovery_config VALUES (?,?,?,?,?)",(run_id,'Construction','Dallas','month','[]'))
            self.result_id=self.store.db.execute("""INSERT INTO discovery_results
              (run_id,url,title,snippet,companies_json,signals_json,places_json,query)
              VALUES (?,?,?,?,?,?,?,?)""",(run_id,'https://news.example/project','Developer breaks ground on apartments',
              'Developer started a 400-unit project.','[]','["mobilization"]','["Dallas"]','groundbreaking')).lastrowid
            classification={'source_index':0,'company_name':'Example Developer','company_is_construction_business':True,
              'source_is_company_owned':False,'company_website':None,'signal_type':'project_start',
              'event_date':'2026-10-01','field_roles':['construction'],'evidence_strength':'strong',
              'evidence_reliability':'credible_secondary','evidence_summary':'Project started.','rejection_reason':None}
            score={'passes':True,'total':87}
            self.store.db.execute("""INSERT INTO llm_classifications
              (result_id,status,model,prompt_version,classification_json,score,score_json,classified_at)
              VALUES (?,'completed','gpt-4o-mini','test',?,87,?,?)""",
              (self.result_id,json.dumps(classification),json.dumps(score),now()))
            self.store.db.execute("INSERT INTO contractor_verifications(result_id,status,created_at) VALUES (?,'running',?)",(self.result_id,now()))
            apify_run=self.store.db.execute("""INSERT INTO apify_runs
              (result_id,mode,target_url,status,created_at,finished_at)
              VALUES (?,'project',?,'completed',?,?)""",
              (self.result_id,'https://news.example/project',now(),now())).lastrowid
            self.store.db.execute("""INSERT INTO apify_evidence
              (run_id,url,title,content,created_at) VALUES (?,?,?,?,?)""",
              (apify_run,'https://permit.example/record','Permit record',
               'A permit record exists, but this excerpt does not name a contractor.',now()))

    def tearDown(self): self.store.close(); self.temp.cleanup()

    def test_targeted_search_distinguishes_developer_and_contractor(self):
        received={}
        def search(body,key):
            return {'results':[{'url':'https://developer.example/news/project','title':'Official project announcement',
              'content':'Example Developer names Atlas Builders as general contractor.'}],'usage':{'credits':1}}
        def model(body,key):
            received.update(json.loads(body['input']))
            urls={item['url'] for item in received['evidence']}
            if 'https://developer.example/news/project' not in urls:
                value={'contractor_name':None,'developer_name':'Example Developer',
                  'project_name':'Apartment project','project_address':None,
                  'contractor_status':'unresolved','confidence':'unresolved',
                  'explanation':'The current evidence does not name the contractor.','evidence_urls':[]}
                return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
            value={'contractor_name':'Atlas Builders','developer_name':'Example Developer',
              'project_name':'Apartment project','project_address':'100 Test St, Dallas, TX',
              'contractor_status':'confirmed',
              'confidence':'confirmed','explanation':'The developer explicitly names the general contractor.',
              'evidence_urls':['https://developer.example/news/project/']}
            return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
        value=run(self.store,self.result_id,'search-key','model-key',search,model)
        self.assertEqual(value['contractor_name'],'Atlas Builders')
        saved=self.store.rows('SELECT * FROM contractor_verifications WHERE result_id=?',(self.result_id,))[0]
        self.assertEqual(saved['confidence'],'confirmed')
        self.assertEqual(value['evidence_urls'],['https://developer.example/news/project'])
        self.assertEqual(len(self.store.rows('SELECT * FROM contractor_evidence')),3)
        self.assertEqual({item['url'] for item in received['evidence']},
          {'https://developer.example/news/project'})
        attempts=len(self.store.rows('SELECT * FROM provider_attempts'))
        again=run(self.store,self.result_id,'search-key','model-key',
          lambda body,key: self.fail('retry should reuse purchased evidence'),model)
        self.assertEqual(again['contractor_name'],'Atlas Builders')
        self.assertEqual(len(self.store.rows('SELECT * FROM provider_attempts')),attempts)

    def test_browser_starts_in_place_and_status_returns_result(self):
        def search(body,key):
            return {'results':[{'url':'https://developer.example/news/project','title':'Official announcement',
              'content':'Example Developer names Atlas Builders as general contractor.'}],'usage':{'credits':1}}
        def model(body,key):
            evidence=json.loads(body['input'])['evidence']
            if not any(item['url']=='https://developer.example/news/project' for item in evidence):
                value={'contractor_name':None,'developer_name':'Example Developer',
                  'project_name':'Apartment project','project_address':None,
                  'contractor_status':'unresolved','confidence':'unresolved',
                  'explanation':'No contractor is proven yet.','evidence_urls':[]}
                return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
            value={'contractor_name':'Atlas Builders','developer_name':'Example Developer',
              'project_name':'Apartment project','project_address':'100 Test St, Dallas, TX',
              'contractor_status':'confirmed',
              'confidence':'confirmed','explanation':'The developer explicitly names the general contractor.',
              'evidence_urls':['https://developer.example/news/project']}
            return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
        controller=ResearchController(self.path,search_transport=search)
        controller.classifier_transport=model
        controller.connection.configure('test-search-key')
        controller.classifier_connection.configure('test-openai-key-long-enough')
        server=HTTPServer(('127.0.0.1',0),handler(self.path,controller))
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base+'/classification') as response:
                page=response.read().decode()
            csrf=re.search("name='csrf' value='([^']+)'",page)[1]
            data=urlencode({'csrf':csrf,'result_id':self.result_id,'return_to':'classification'}).encode()
            request=Request(base+'/contractor/verify',data=data,headers={
              'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'ContractorLookup'})
            with urlopen(request) as response:
                self.assertEqual(response.status,202)
                self.assertEqual(json.load(response)['status'],'queued')
            controller.threads[-1].join(5)
            with urlopen(base+f'/contractor/status?id={self.result_id}') as response:
                status=json.load(response)
            self.assertEqual(status['status'],'completed')
            self.assertEqual(status['contractor_name'],'Atlas Builders')
            self.assertEqual(status['contractor_status'],'confirmed')
            self.assertEqual(status['evidence'][0]['title'],'Official announcement')
        finally:
            server.shutdown(); thread.join(); server.server_close()

    def test_ai_can_distinguish_pending_vote_from_final_award(self):
        def search(body,key):
            return {'results':[{'url':'https://city.example/agenda','title':'Council agenda',
              'content':'Council will consider awarding the project to Atlas Builders.'}]}
        def model(body,key):
            evidence=json.loads(body['input'])['evidence']
            if not any(item['url']=='https://city.example/agenda' for item in evidence):
                value={'contractor_name':None,'developer_name':'Example Developer',
                  'project_name':'Apartment project','project_address':None,
                  'contractor_status':'unresolved','confidence':'unresolved',
                  'explanation':'No decision record is present.','evidence_urls':[]}
                return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
            value={'contractor_name':'Atlas Builders','developer_name':'Example Developer',
              'project_name':'Apartment project','project_address':None,
              'contractor_status':'pending_award','confidence':'probable',
              'explanation':'The council has not yet approved the proposed award.',
              'evidence_urls':['https://city.example/agenda']}
            return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
        value=run(self.store,self.result_id,'search-key','model-key',search,model)
        self.assertEqual(value['contractor_status'],'pending_award')
        self.assertEqual(value['confidence'],'probable')

    def test_hiring_lead_is_not_eligible_for_contractor_lookup(self):
        row=self.store.rows('SELECT classification_json FROM llm_classifications WHERE result_id=?',(self.result_id,))[0]
        value=json.loads(row['classification_json']); value['signal_type']='bulk_hiring'
        with self.store.db:
            self.store.db.execute('UPDATE llm_classifications SET classification_json=? WHERE result_id=?',
                                  (json.dumps(value),self.result_id))
        with self.assertRaisesRegex(ValueError,'only for project-start or contract-award'):
            eligible(self.store,self.result_id)

    def test_audit_rejects_developer_as_unproven_contractor(self):
        def search(body,key):
            return {'results': []}
        def model(body,key):
            audit='Independently audit' in body['instructions']
            evidence=json.loads(body['input'])['evidence']
            value={'contractor_name':None if audit else 'Example Developer',
                'developer_name':'Example Developer','project_name':'Apartment project',
                'project_address':None,'contractor_status':'unresolved' if audit else 'confirmed',
                'confidence':'unresolved' if audit else 'confirmed',
                'explanation':'Developer announcement does not establish contractor role.' if audit else 'Construction started.',
                'evidence_urls':[] if audit else [evidence[0]['url']]}
            return {'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
        value=run(self.store,self.result_id,'search-key','model-key',search,model)
        self.assertEqual(value['contractor_status'],'unresolved')
        self.assertIsNone(value['contractor_name'])

    def test_confirmed_result_requires_named_project_and_citation(self):
        def search(body,key):
            return {'results':[{'url':'https://city.example/award','title':'Award notice',
              'content':'Atlas Builders received the construction contract.'}]}
        def model(body,key):
            evidence=json.loads(body['input'])['evidence']
            if not any(item['url']=='https://city.example/award' for item in evidence):
                value={'contractor_name':None,'developer_name':'Example Developer',
                  'project_name':'Apartment project','project_address':None,
                  'contractor_status':'unresolved','confidence':'unresolved',
                  'explanation':'No award record is present.','evidence_urls':[]}
                return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
            value={'contractor_name':'Atlas Builders','developer_name':'Example Developer',
              'project_name':None,'project_address':None,'contractor_status':'confirmed',
              'confidence':'confirmed','explanation':'A contractor is named without a project.',
              'evidence_urls':['https://city.example/award']}
            return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
        with self.assertRaisesRegex(ValueError,'requires a named project'):
            run(self.store,self.result_id,'search-key','model-key',search,model)

    def test_duplicate_source_reuses_completed_project_without_new_request(self):
        def search(body,key):
            return {'results':[{'url':'https://developer.example/news/project','title':'Official project announcement',
              'content':'Example Developer names Atlas Builders as general contractor.'}]}
        def model(body,key):
            evidence=json.loads(body['input'])['evidence']
            if not any(item['url']=='https://developer.example/news/project' for item in evidence):
                value={'contractor_name':None,'developer_name':'Example Developer',
                  'project_name':'Apartment project','project_address':None,
                  'contractor_status':'unresolved','confidence':'unresolved',
                  'explanation':'No contractor is proven yet.','evidence_urls':[]}
                return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
            value={'contractor_name':'Atlas Builders','developer_name':'Example Developer',
              'project_name':'Apartment project','project_address':'100 Test St, Dallas, TX',
              'contractor_status':'confirmed','confidence':'confirmed',
              'explanation':'The developer explicitly names the project contractor.',
              'evidence_urls':['https://developer.example/news/project']}
            return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
        run(self.store,self.result_id,'search-key','model-key',search,model)
        with self.store.db:
            second_run=self.store.db.execute("""INSERT INTO research_runs
              (request_key,query,signal,source_ids,max_pages,max_depth,status,created_at)
              VALUES ('duplicate-run','', 'mobilization','[]',0,0,'completed',?)""",(now(),)).lastrowid
            self.store.db.execute("INSERT INTO discovery_config VALUES (?,?,?,?,?)",
                (second_run,'Construction','Dallas','month','[]'))
            duplicate=self.store.db.execute("""INSERT INTO discovery_results
              (run_id,url,title,snippet,companies_json,signals_json,places_json,query)
              SELECT ?,url,title,snippet,companies_json,signals_json,places_json,query
              FROM discovery_results WHERE id=?""",(second_run,self.result_id)).lastrowid
            original=self.store.rows('SELECT * FROM llm_classifications WHERE result_id=?',(self.result_id,))[0]
            self.store.db.execute("""INSERT INTO llm_classifications
              (result_id,status,model,prompt_version,classification_json,score,score_json,classified_at)
              VALUES (?,?,?,?,?,?,?,?)""",(duplicate,original['status'],original['model'],
              original['prompt_version'],original['classification_json'],original['score'],
              original['score_json'],original['classified_at']))
        before=len(self.store.rows('SELECT * FROM provider_attempts'))
        source=reuse_completed(self.store,duplicate,eligible(self.store,duplicate))
        self.assertEqual(source,self.result_id)
        self.assertEqual(len(self.store.rows('SELECT * FROM provider_attempts')),before)
        copied=self.store.rows('SELECT * FROM contractor_verifications WHERE result_id=?',(duplicate,))[0]
        self.assertEqual(copied['contractor_name'],'Atlas Builders')
        self.assertEqual(copied['status'],'completed')

    def test_ranked_plan_uses_documented_domain_preferences(self):
        row=eligible(self.store,self.result_id)
        private=search_plan(row)
        self.assertEqual([item[0] for item in private],[
          'issued_permit','owner_developer_announcement','planning_and_agenda_records',
          'trade_publication','broad_web_fallback'])
        self.assertEqual(private[0][1]['include_domains_mode'],'prefer')
        self.assertNotIn('site:',private[0][1]['query'])
        row['classification']['signal_type']='contract_award'
        public=search_plan(row)
        self.assertEqual(public[0][0],'official_final_award')
        self.assertEqual(public[1][0],'bid_tabulation_and_minutes')

    def test_ranked_search_stops_after_first_confirmed_method(self):
        searched=[]; model_calls=[]
        def search(body,key):
            searched.append(body['query'])
            return {'results':[{'url':'https://dallasopendata.com/permit/1','title':'Issued permit',
              'content':'Issued permit for Apartment project names Atlas Builders as general contractor.'}],
              'usage':{'credits':1}}
        def model(body,key):
            evidence=json.loads(body['input'])['evidence']; model_calls.append(evidence)
            permit=next((item for item in evidence if item['url']=='https://dallasopendata.com/permit/1'),None)
            if permit:
                value={'contractor_name':'Atlas Builders','developer_name':'Example Developer',
                  'project_name':'Apartment project','project_address':'100 Test St, Dallas, TX',
                  'contractor_status':'confirmed','confidence':'confirmed',
                  'explanation':'The issued permit names the general contractor.',
                  'evidence_urls':[permit['url']]}
            else:
                value={'contractor_name':None,'developer_name':'Example Developer',
                  'project_name':'Apartment project','project_address':None,
                  'contractor_status':'unresolved','confidence':'unresolved',
                  'explanation':'Existing evidence is insufficient.','evidence_urls':[]}
            return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
        value=run(self.store,self.result_id,'search-key','model-key',search,model)
        self.assertEqual(value['contractor_status'],'confirmed')
        self.assertEqual(len(searched),1)
        self.assertEqual(len(model_calls),3)
        attempt=self.store.rows('SELECT * FROM contractor_method_attempts')[0]
        self.assertEqual(attempt['method_id'],'issued_permit')
        self.assertEqual(attempt['status'],'completed')


if __name__=='__main__': unittest.main()
