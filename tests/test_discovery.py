import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import HTTPServer
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

from leadintel.discovery import company_candidates, details, flag_candidate, reserve_search, safe_result_url, request_search
from leadintel.discovery_ui import home
from leadintel.query_bank import query_bank, selected_plan, tested_top_queries, TRADES, SIGNALS
from leadintel.research import ResearchController
from leadintel.store import Store
from leadintel.web import handler


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'engine.sqlite'
        self.store=Store(self.path)
        self.calls=[]
        self.controller=ResearchController(self.path,search_transport=self.provider)
        self.controller.connection.configure('test-only-credential')
        self.controller.classifier_connection.configure('test-only-openai-classifier-key')
        self.controller.classifier_transport=self.classifier

    def tearDown(self):
        for worker in self.controller.threads:
            worker.join(5)
        self.store.close()
        self.temp.cleanup()

    def provider(self,body,key):
        self.calls.append(body)
        return {'usage':{'credits':1},'results':[
            {'url':'https://newfirm.example/news?utm_source=feed','title':'Orion Mechanical is hiring in Dallas', 'content':'Orion Mechanical is hiring field workers for construction projects in Dallas.'},
            {'url':'https://journal.example/orion','title':'Local company hiring', 'content':'Orion Mechanical is hiring construction workers in Dallas.'},
            {'url':'https://jobboard.example/search','title':'Construction jobs in Dallas', 'content':'Browse construction jobs from employers. Now hiring.'},
            {'url':'https://another.example/news','title':'Sable Construction awarded project', 'content':'Sable Construction was awarded a Dallas construction contract.'},
        ]}

    def classifier(self,body,key):
        records=json.loads(body['input'])['records']
        outputs=[]
        for row in records:
            text=row['title']+' '+row['snippet']
            if 'Orion Mechanical' in text:
                value=dict(company_name='Orion Mechanical',company_is_construction_business=True,
                    source_is_company_owned='newfirm.example' in row['source_url'],
                    company_website='https://newfirm.example/' if 'newfirm.example' in row['source_url'] else None,
                    signal_type='bulk_hiring',event_date='2026-10-14',field_roles=['field workers','construction workers'],
                    evidence_strength='strong',evidence_reliability='primary',
                    evidence_summary='Orion explicitly reports hiring multiple construction field roles.',rejection_reason=None)
            elif 'Sable Construction' in text:
                value=dict(company_name='Sable Construction',company_is_construction_business=True,
                    source_is_company_owned=False,company_website=None,
                    signal_type='contract_award',event_date='2026-10-14',field_roles=[],
                    evidence_strength='strong',evidence_reliability='credible_secondary',
                    evidence_summary='Sable was awarded a construction contract.',rejection_reason=None)
            else:
                value=dict(company_name=None,company_is_construction_business=False,
                    source_is_company_owned=False,company_website=None,
                    signal_type='none',event_date=None,field_roles=[],evidence_strength='none',
                    evidence_reliability='job_board',evidence_summary=None,
                    rejection_reason='Generic job-board result with no explicit employer signal.')
            outputs.append(dict(source_index=row['source_index'],**value))
        return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'results':outputs})}]}]}

    def form(self,key='unique-discovery-test-001',**kwargs):
        fields={'query_set':['full'],'trade':['construction'],'location':['Dallas Texas'],'signal':['hiring'],
                'period':['month'],'query_ids':['construction:hiring:0','construction:hiring:1'],'request_key':[key]}
        fields.update(kwargs)
        return fields

    def test_discovers_unseeded_company_without_supplied_sources(self):
        ident=self.controller.start_discovery(self.form(),launch=False)
        self.controller.run(ident)
        result=details(self.store,ident)
        self.assertEqual(result['run']['status'],'completed')
        self.assertEqual([c['name'] for c in result['companies']],['Orion Mechanical','Sable Construction'])
        self.assertEqual(len(result['companies'][0]['evidence']),2)
        self.assertEqual(result['result_count'],4)
        self.assertEqual(len(result['unresolved']),1)
        self.assertEqual(self.store.rows('SELECT * FROM sources'),[])
        self.assertEqual(self.store.rows('SELECT * FROM leads'),[])
        self.assertEqual(self.store.enrichment_tasks(),[])
        self.assertEqual(len(self.calls),2)
        for body in self.calls:
            self.assertNotIn('include_domains',body)
            self.assertNotIn('KPost',body['query'])
            self.assertEqual(body['search_depth'],'basic')
            self.assertFalse(body['auto_parameters'])

    def test_missing_key_blocks_before_reservation_and_network(self):
        self.controller.connection.clear()
        with patch.dict('os.environ',{},clear=True),self.assertRaisesRegex(ValueError,'Connect Tavily'):
            self.controller.start_discovery(self.form())
        self.assertEqual(self.calls,[])
        self.assertEqual(self.store.rows('SELECT * FROM provider_attempts'),[])

    def test_missing_classifier_does_not_disable_company_search(self):
        self.controller.classifier_connection.clear()
        body=home(self.store,'csrf-token',self.controller.connection,self.controller.classifier_connection)
        self.assertIn("id='run-queries' data-ready='1'",body)
        self.assertIn('You can still run the search now',body)
        self.assertIn('save results for later classification',body)

    def test_candidates_are_not_contacts_and_flag_does_not_enrich(self):
        ident=self.controller.start_discovery(self.form(),launch=False)
        self.controller.run(ident)
        company=details(self.store,ident)['companies'][0]
        lead=flag_candidate(self.store,company['evidence'][0]['id'],company['identity_key'])
        self.assertEqual(self.store.rows('SELECT * FROM leads')[0]['status'],'flagged')
        self.assertEqual(self.store.enrichment_tasks(),[])
        self.store.begin_qualification(lead)
        self.assertEqual(len(self.store.enrichment_tasks()),1)

    def test_signal_predicates_and_generic_publishers_are_not_company_names(self):
        cases=[('Construction jobs','Construction jobs in Dallas. Now hiring.'),
               ('Construction Dive','Construction Dive reports hiring trends.'),
               ('Orion Mechanical','Orion Mechanical is not hiring construction workers.'),
               ('Sable Construction awarded a project','Sable Construction was awarded a contract.')]
        for title,snippet in cases:
            with self.subTest(title=title):
                self.assertEqual(company_candidates(title,snippet,'hiring')[0],[])
        companies,_=company_candidates('Careers | NovelWorks','Our mechanical construction company is hiring in Dallas.','hiring')
        self.assertEqual(companies[0]['name'],'NovelWorks')

    def test_every_trade_and_signal_has_twenty_distinct_queries(self):
        for trade in TRADES:
            for signal in SIGNALS:
                bank=query_bank(trade,'Dallas Texas',signal)
                self.assertEqual(len(bank),20)
                self.assertEqual(len({r['query'] for r in bank}),20)
                self.assertTrue(all('Dallas Texas' in r['query'] for r in bank))
        bank=query_bank('roofing','DFW','all')
        self.assertEqual(len(bank),80)
        self.assertEqual({r['signal'] for r in bank[:4]},set(SIGNALS))
        self.assertTrue(any('"Fort Worth" Texas' in r['query'] for r in bank))
        self.assertFalse(any('"DFW"' in r['query'] for r in bank))

    def test_tested_top_fifteen_are_ranked_and_reusable(self):
        bank=tested_top_queries('construction','DFW')
        self.assertEqual(len(bank),15)
        self.assertEqual([r['tested_rank'] for r in bank],list(range(1,16)))
        self.assertEqual(len({r['query'] for r in bank}),15)
        self.assertEqual(set(r['signal'] for r in bank),set(SIGNALS))
        self.assertTrue(all('"Dallas Fort Worth" Texas' in r['query'] for r in bank))
        self.assertIn('awarded contract',bank[0]['query'])
        self.assertEqual(bank[9]['include_domains'],['constructiondive.com','enr.com'])
        self.assertEqual(sum(r['signal']=='hiring' for r in bank),2)
        plan=selected_plan('construction','DFW','all','','month',
                           [r['id'] for r in bank[:10]],'tested')
        self.assertEqual([r['query'] for r in plan],[r['query'] for r in bank[:10]])
        self.assertEqual(plan[9]['include_domains'],['constructiondive.com','enr.com'])
        self.assertTrue(all('indeed.com' in r.get('exclude_domains',[]) for r in plan[:9]))

    def test_ten_selected_queries_execute_exact_preview_and_deduplicate_results(self):
        bank=query_bank('roofing','Dallas Texas','all','schools')
        chosen=bank[7:17]
        form=self.form(trade=['roofing'],signal=['all'],query=['schools'],query_ids=[r['id'] for r in chosen])
        ident=self.controller.start_discovery(form,launch=False)
        stored=json.loads(details(self.store,ident)['config']['requests_json'])
        self.assertEqual([r['query'] for r in stored],[r['query'] for r in chosen])
        self.controller.run(ident)
        self.assertEqual(self.calls,stored)
        self.assertEqual(len(self.calls),10)
        result=details(self.store,ident)
        self.assertEqual(result['run']['status'],'completed')
        self.assertEqual(result['result_count'],4)
        self.assertEqual(len(result['companies']),2)
        self.assertEqual(sum(a['reserved_credits'] for a in result['attempts']),10)

    def test_invalid_selections_never_create_a_run_or_charge(self):
        selections=[[],['construction:hiring:0']*2,
                    [f'construction:hiring:{i}' for i in range(11)],
                    ['construction:hiring:99'],['roofing:hiring:0'],['construction:award:0']]
        for ids in selections:
            with self.subTest(ids=ids),self.assertRaises(ValueError):
                self.controller.start_discovery(self.form(query_ids=ids),launch=False)
        self.assertEqual(self.store.rows('SELECT * FROM research_runs'),[])
        self.assertEqual(self.calls,[])

    def test_single_query_and_invalid_window(self):
        plan=selected_plan('civil','Houston Texas','award','','week',['civil:award:19'],'full')
        self.assertEqual(len(plan),1)
        self.assertIn('Houston Texas',plan[0]['query'])
        self.assertEqual(plan[0]['time_range'],'week')
        with self.assertRaises(ValueError):
            selected_plan('civil','Houston','award','','forever',['civil:award:19'],'full')

    def test_insufficient_budget_rejects_entire_batch_before_creating_run(self):
        ident=self.controller.start_discovery(self.form(),launch=False)
        self.controller.stop(ident)
        self.controller.run(ident)
        for _ in range(25):
            reserve_search(self.store,ident,'already used')
        with self.assertRaisesRegex(ValueError,'only 5 remain'):
            self.controller.start_discovery(self.form('second-batch-request-001',
                query_ids=[f'construction:hiring:{i}' for i in range(10)]),launch=False)
        self.assertEqual(len(self.store.rows('SELECT * FROM research_runs')),1)
        self.assertEqual(self.calls,[])

    def test_budget_includes_failures_and_blocks_before_network(self):
        ident=self.controller.start_discovery(self.form(),launch=False)
        for _ in range(30):
            reserve_search(self.store,ident,'test')
        self.controller.run(ident)
        self.assertEqual(self.calls,[])
        self.assertIn('budget exhausted',details(self.store,ident)['run']['note'])

    def test_provider_error_is_visible_and_no_mock_results_are_substituted(self):
        def fail(body,key):
            raise ValueError('Invalid credential '+key)
        self.controller.search_transport=fail
        ident=self.controller.start_discovery(self.form(),launch=False)
        self.controller.run(ident)
        result=details(self.store,ident)
        self.assertEqual(result['run']['status'],'failed')
        self.assertEqual(result['companies'],[])
        self.assertNotIn('test-only-credential',json.dumps(result))
        self.assertEqual(len(result['attempts']),1)

    def test_stop_retains_first_response_and_prevents_next_search(self):
        entered,release=threading.Event(),threading.Event()
        def blocking(body,key):
            entered.set()
            release.wait(5)
            return self.provider(body,key)
        self.controller.search_transport=blocking
        ident=self.controller.start_discovery(self.form())
        self.assertTrue(entered.wait(5))
        self.controller.stop(ident)
        release.set()
        self.controller.threads[-1].join(5)
        result=details(self.store,ident)
        self.assertEqual(result['run']['status'],'cancelled')
        self.assertEqual(len(self.calls),1)
        self.assertEqual(len(result['companies']),2)

    def test_repeat_submission_does_not_reserve_extra_searches(self):
        ident=self.controller.start_discovery(self.form(),launch=False)
        self.assertEqual(self.controller.start_discovery(self.form(),launch=False),ident)
        with self.assertRaises(ValueError):
            self.controller.start(self.form('different-crawl-request',sources=['registry:kpost']),launch=False)

    def test_result_links_drop_tracking_and_reject_unsafe_destinations(self):
        self.assertEqual(safe_result_url('https://example.com/jobs?jk=123&utm_source=a#x'),'https://example.com/jobs?jk=123')
        for url in ['javascript:alert(1)','http://127.0.0.1/x','http://[::1]/','http://user:pass@example.com','https://example.com:1234']:
            self.assertIsNone(safe_result_url(url))

    def test_home_is_company_discovery_without_company_checklist(self):
        server=HTTPServer(('127.0.0.1',0),handler(self.path,self.controller))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base) as response:
                body=response.read().decode()
            self.assertIn('Find companies',body)
            self.assertNotIn('KPost',body)
            self.assertNotIn('BakerTriangle',body)
            self.assertNotIn('test-only-credential',body)
            self.assertEqual(body.count("name='query_ids'"),15)
            self.assertIn('Choose up to 10 queries',body)
            self.assertIn('Tested top 15',body)
            with urlopen(base+'/?trade=electrical&signal=all&location=Austin&query=schools') as response:
                preview=response.read().decode()
                self.assertIn('15 options',preview)
                self.assertIn('electrical contractor &quot;awarded contract&quot; construction Austin schools',preview)
            with urlopen(base+'/?query_set=full&trade=electrical&signal=all&location=Austin&query=schools') as response:
                preview=response.read().decode()
                self.assertIn('80 options',preview)
            self.assertEqual(self.calls,[])
            self.assertEqual(self.store.rows('SELECT * FROM provider_attempts'),[])
            csrf=re.search("name='csrf' value='([^']+)'",body)[1]
            key=re.search("name='request_key' value='([^']+)'",body)[1]
            form=self.form(key,csrf=[csrf])
            req=Request(base+'/discover/start',data=urlencode(form,doseq=True).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
            with urlopen(req) as response:
                destination=response.url
                self.assertIn('Companies found',response.read().decode())
            for worker in self.controller.threads:
                worker.join(5)
            with urlopen(destination) as response:
                self.assertIn('Orion Mechanical',response.read().decode())
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_transport_uses_fixed_host_and_never_persists_provider_error_body(self):
        with patch('urllib.request.OpenerDirector.open',side_effect=HTTPError('https://api.tavily.com/search',401,'secret response',{},None)):
            with self.assertRaisesRegex(ValueError,'rejected the API key'):
                request_search({'query':'construction'},'test-only-credential')


if __name__=='__main__':
    unittest.main()
