import re
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import HTTPServer
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from leadintel.crawler import Response
from leadintel.research import ResearchController, run_details
from leadintel.store import Store
from leadintel.web import handler


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'research.sqlite'
        self.calls=[]
        self.controller=ResearchController(self.path,self.transport,delay=0)
        self.store=Store(self.path)

    def tearDown(self):
        for thread in self.controller.threads:
            thread.join(5)
        self.store.close()
        self.temp.cleanup()

    def transport(self,url,limit):
        self.calls.append(url)
        if url.endswith('robots.txt'):
            return Response(404,b'',{})
        return Response(200,b'<title>Contractor hiring in Dallas</title><p>Hiring field workers in Dallas</p><a href="/news/next">Next</a>',{'content-type':'text/html'})

    def form(self,key='test-request-key-001',**values):
        data={'request_key':[key],'sources':['monitor:groundbreak_dfw_started'],'max_pages':['2'],'max_depth':['1'], 'signal':['hiring'],'geography':['Dallas']}
        data.update(values)
        return data

    def test_fresh_crawl_has_run_scoped_results_and_no_contact_enrichment(self):
        self.store.ingest(None,'https://old.example.org','Old hiring Dallas','hiring Dallas',signals=['hiring'],geography=['Dallas'])
        ident=self.controller.start(self.form(),launch=False)
        self.controller.run(ident)
        run=run_details(self.store,ident)
        self.assertEqual(run['status'],'completed')
        self.assertEqual(run['sources'][0]['prefix'],'/dfw/')
        self.assertEqual(len(run['results']),1)
        self.assertTrue(self.calls)
        self.assertFalse(any('old.example' in d['url'] for d in run['results']))
        self.assertEqual(self.store.enrichment_tasks(),[])
        self.assertEqual(len(self.store.rows('SELECT * FROM leads')),0)

    def test_repeat_submission_is_idempotent_and_active_run_blocks_new_one(self):
        ident=self.controller.start(self.form(),launch=False)
        self.assertEqual(self.controller.start(self.form(),launch=False),ident)
        with self.assertRaisesRegex(ValueError,'already active'):
            self.controller.start(self.form('different-request-002'),launch=False)

    def test_stop_before_start_sends_no_requests(self):
        ident=self.controller.start(self.form(),launch=False)
        self.controller.stop(ident)
        self.controller.run(ident)
        self.assertEqual(self.calls,[])
        self.assertEqual(run_details(self.store,ident)['status'],'cancelled')

    def test_stop_during_request_prevents_next_request(self):
        entered,release=threading.Event(),threading.Event()
        def slow(url,limit):
            entered.set()
            release.wait(5)
            return self.transport(url,limit)
        self.controller.transport=slow
        ident=self.controller.start(self.form())
        self.assertTrue(entered.wait(5))
        self.controller.stop(ident)
        release.set()
        self.controller.threads[0].join(5)
        self.assertEqual(len(self.calls),1) # Only robots request was in flight.
        self.assertEqual(run_details(self.store,ident)['status'],'cancelled')

    def test_multi_site_page_cap_is_shared_and_filters_do_not_hide_access_records(self):
        ident=self.controller.start(self.form(sources=['monitor:groundbreak_dfw_started','monitor:dfw_planroom_public'],query=['nonexistent'],max_pages=['3']),launch=False)
        self.controller.run(ident)
        run=run_details(self.store,ident)
        self.assertLessEqual(len(run['documents']),3)
        self.assertEqual(len(run['jobs']),2)
        self.assertEqual(run['results'],[])
        self.assertTrue(run['attempts'])

    def test_failed_robots_is_reported_without_fake_results(self):
        self.controller.transport=lambda u,l:Response(403,b'',{})
        ident=self.controller.start(self.form(),launch=False)
        self.controller.run(ident)
        run=run_details(self.store,ident)
        self.assertEqual(run['status'],'completed_with_gaps')
        self.assertEqual(run['documents'],[])
        self.assertIn('Robots unavailable',run['jobs'][0]['note'])

    def test_restart_marks_unfinished_runs_without_replaying_network(self):
        ident=self.controller.start(self.form(),launch=False)
        self.controller.recover()
        self.assertEqual(run_details(self.store,ident)['status'],'interrupted')
        self.assertEqual(self.calls,[])

    def test_invalid_scope_rejected_before_network(self):
        for values in [dict(sources=[]),dict(sources=['not-real']),dict(max_pages=['21']),dict(custom_url=['http://127.0.0.1/']),dict(custom_url=['https://instagram.com/account/']),dict(geography=['bad'])]:
            with self.subTest(values=values),self.assertRaises(ValueError):
                self.controller.start(self.form(**values),launch=False)
        self.assertEqual(self.calls,[])

    def test_duplicate_worker_cannot_finish_active_run(self):
        ident=self.controller.start(self.form(),launch=False)
        with self.store.db:
            self.store.db.execute("UPDATE research_runs SET status='running' WHERE id=?",(ident,))
        self.controller.run(ident)
        self.assertEqual(run_details(self.store,ident)['status'],'running')
        self.assertEqual(self.calls,[])

    def test_browser_start_runs_background_collection_with_csrf_and_history(self):
        server=HTTPServer(('127.0.0.1',0),handler(self.path,self.controller))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base+'/monitor') as response:
                body=response.read().decode()
            self.assertIn('Start research',body)
            self.assertIn('Groundbreak',body)
            self.assertIn('https://pro.groundbreak.city/dfw/projects?stage=started',body)
            self.assertIn('Open exact listing page',body)
            self.assertIn('SaunaNews',body)
            self.assertNotIn('KPost Company',body)
            self.assertIn('Company websites and general homepages are intentionally excluded',body)
            csrf=re.search("name='csrf' value='([^']+)'",body)[1]
            key=re.search("name='request_key' value='([^']+)'",body)[1]
            form=self.form(key,csrf=[csrf])
            request=Request(base+'/research/start',data=urlencode(form,doseq=True).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
            with urlopen(request) as response:
                self.assertIn('/research/run?id=',response.url)
                self.assertIn('Research #',response.read().decode())
            for worker in self.controller.threads:
                worker.join(5)
            self.assertEqual(len(run_details(self.store,1)['results']),1)
            # Invalid CSRF cannot trigger a new crawl.
            request=Request(base+'/research/start',data=b'request_key=invalid',headers={'Content-Type':'application/x-www-form-urlencoded'})
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code,403)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__=='__main__':
    unittest.main()
