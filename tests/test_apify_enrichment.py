import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from leadintel.apify_enrichment import enrichment_plan
from leadintel.research import ResearchController
from leadintel.store import Store, now


class ApifyEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'apify.sqlite'
        self.store=Store(self.path)
        with self.store.db:
            run=self.store.db.execute("""INSERT INTO research_runs
              (request_key,query,signal,source_ids,max_pages,max_depth,status,created_at)
              VALUES ('apify-test-run','', 'award','[]',0,0,'completed',?)""",(now(),)).lastrowid
            self.store.db.execute("INSERT INTO discovery_config VALUES (?,?,?,?,?)",
                (run,'Construction','Dallas','month','[]'))
            self.result_id=self.store.db.execute("""INSERT INTO discovery_results
              (run_id,url,title,snippet,companies_json,signals_json,places_json,query)
              VALUES (?,?,?,?,?,?,?,?)""",(run,'https://atlas.example/news/award','Atlas wins project',
              'Atlas Builders won a construction contract.','[]','["award"]','["Dallas"]','award')).lastrowid
            classification={'source_index':0,'company_name':'Atlas Builders',
                'company_is_construction_business':True,'source_is_company_owned':True,
                'company_website':'https://atlas.example/','signal_type':'contract_award',
                'event_date':'2026-10-01','field_roles':[],'evidence_strength':'strong',
                'evidence_reliability':'primary','evidence_summary':'Atlas won a contract.',
                'rejection_reason':None}
            score={'total':90,'passes':True,'threshold':65,'eligible_company':True,'components':{}}
            self.store.db.execute("""INSERT INTO llm_classifications
              (result_id,status,model,prompt_version,classification_json,score,score_json,classified_at)
              VALUES (?,'completed','mock','v2',?,?,?,?)""",
              (self.result_id,json.dumps(classification),90,json.dumps(score),now()))
        self.controller=ResearchController(self.path)
        self.controller.apify_connection.configure('test-only-apify-token-long-enough')
        self.calls=[]
        def transport(body,key):
            self.calls.append(body)
            return [{'url':'https://atlas.example/news/award','title':'Award details',
                     'markdown':'Atlas Builders won the project and starts next month.'}]
        self.controller.apify_transport=transport

    def tearDown(self):
        for worker in self.controller.threads:
            worker.join(5)
        self.store.close()
        self.temp.cleanup()

    def test_project_and_company_plans_are_bounded(self):
        project=enrichment_plan(self.store,self.result_id,'project')
        self.assertEqual(project['input']['maxCrawlPages'],1)
        self.assertEqual(project['max_total_charge_usd'],0.25)
        company=enrichment_plan(self.store,self.result_id,'company')
        self.assertEqual(company['input']['maxCrawlPages'],5)
        self.assertTrue(any('careers' in pattern for pattern in company['input']['includeUrlGlobs']))

    def test_only_passing_result_can_run_and_token_is_not_persisted(self):
        run_id=self.controller.start_apify(self.result_id,'project',launch=False)
        self.controller.run_apify(run_id)
        run=self.store.rows('SELECT * FROM apify_runs WHERE id=?',(run_id,))[0]
        self.assertEqual(run['status'],'completed')
        self.assertEqual(len(self.store.rows('SELECT * FROM apify_evidence')),1)
        self.assertNotIn('test-only-apify-token',json.dumps(run))
        self.assertEqual(len(self.calls),1)

    def test_database_gate_rejects_below_threshold(self):
        with self.store.db:
            self.store.db.execute('UPDATE llm_classifications SET score=64 WHERE result_id=?',(self.result_id,))
        with self.assertRaisesRegex(sqlite3.IntegrityError,'passing lead score'):
            with self.store.db:
                self.store.db.execute("""INSERT INTO apify_runs
                  (result_id,mode,target_url,status,created_at) VALUES (?,'project',?,'queued',?)""",
                  (self.result_id,'https://atlas.example/news/award',now()))


if __name__=='__main__':
    unittest.main()
