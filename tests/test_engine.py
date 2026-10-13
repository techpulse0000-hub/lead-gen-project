import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from leadintel.__main__ import run_demo
from leadintel.crawler import Crawler, Response, add_source, canonical, public_addresses
from leadintel.providers import search_plan, social_plan
from leadintel.store import Store
from leadintel.web import handler
from leadintel.crawler import classify
from leadintel.profile import load_profile


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"engine.sqlite"
        self.store=Store(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def source(self):
        return add_source(self.store,"Test source","https://public.example.org/news/")

    def test_demo_crawls_and_searches_without_network(self):
        with patch("socket.getaddrinfo",side_effect=AssertionError("No network permitted")):
            result=run_demo(self.store)
        self.assertEqual(result["status"],"completed")
        rows=self.store.search("awarded",signal="award",geography="Collin")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["is_demo"],1)
        self.assertIsNone(rows[0]["event_date"])
        self.assertEqual(rows[0]["access_method"],"synthetic_fixture")
        self.assertEqual(len(self.store.coverage()["attempts"]),4)

    def test_versions_and_repeated_ingest(self):
        a=self.store.ingest(None,"https://example.org/news/1","Award","awarded Dallas contract")
        b=self.store.ingest(None,"https://example.org/news/1","Award","awarded Dallas contract")
        self.assertEqual(a,b)
        self.store.ingest(None,"https://example.org/news/1","Award","New text")
        self.store.ingest(None,"https://example.org/news/1","Award","New text","2026-10-12")
        self.assertEqual(len(self.store.rows("SELECT * FROM versions")),3)
        self.assertEqual(len(self.store.search("New")),1)
        self.assertEqual(self.store.search("Dallas"),[])

    def test_unchanged_document_can_be_reclassified(self):
        self.store.ingest(None,"https://example.org/1","News","Frisco",geography=["Collin"])
        self.store.ingest(None,"https://example.org/1","News","Frisco",geography=["Collin","Denton"])
        self.assertEqual(len(self.store.search("Frisco",geography="Denton")),1)
        self.assertEqual(len(self.store.rows("SELECT * FROM versions")),1)

    def test_flag_is_not_enrichment_and_qualification_is_idempotent(self):
        doc=self.store.ingest(None,"https://example.org/1","Project","Evidence")
        lead=self.store.flag(doc,"Company","Investigate project")
        self.assertEqual(self.store.enrichment_tasks(),[])
        self.assertEqual(self.store.rows("SELECT * FROM enrichment_queue"),[])
        self.store.begin_qualification(lead)
        self.store.begin_qualification(lead)
        self.assertEqual(len(self.store.enrichment_tasks()),1)
        self.assertEqual(len(self.store.rows("SELECT * FROM transitions")),1)
        with self.store.db:
            self.store.db.execute("UPDATE leads SET status='rejected' WHERE id=?", (lead,))
        self.assertEqual(self.store.enrichment_tasks(),[])
        with self.assertRaises(ValueError):
            self.store.begin_qualification(lead)

    def test_concurrent_qualification_creates_single_task(self):
        doc=self.store.ingest(None,"https://example.org/1","Project","Evidence")
        lead=self.store.flag(doc,"Company","Reason")
        def qualify(_):
            s=Store(self.path)
            try:
                return s.begin_qualification(lead)["id"]
            finally:
                s.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids=list(pool.map(qualify,range(8)))
        self.assertEqual(len(set(ids)),1)

    def test_database_rejects_enrichment_for_unqualified_candidate(self):
        import sqlite3
        doc=self.store.ingest(None,"https://example.org/1","Project","Evidence")
        lead=self.store.flag(doc,"Company","Reason")
        with self.assertRaises(sqlite3.IntegrityError),self.store.db:
            self.store.db.execute("INSERT INTO enrichment_queue(lead_id,created_at) VALUES(?,?)", (lead,"test"))

    def test_profiles_are_configurable_and_ambiguous_city_is_preserved(self):
        signals,places=classify("Frisco contractor awarded project")
        self.assertEqual(set(places),{"Collin","Denton"})
        self.assertIn("award",signals)
        custom={"id":"camp","signals":{"season":["registration"]},"geography":{"Test County":["test city"]}}
        self.assertEqual(classify("Registration opens in Test City",custom),(["season"],["Test County"]))

    def test_literal_search_does_not_execute_fts_or_sql(self):
        self.store.ingest(None,"https://example.org/1","Example","Hiring in Dallas")
        for query in ['" OR *','; DROP TABLE documents; --','NEAR(hiring,20)','***']:
            self.store.search(query)
        self.assertEqual(self.store.coverage()["documents"],1)

    def test_private_urls_and_social_pages_blocked(self):
        for url in ["http://127.0.0.1/","http://[::1]/","http://169.254.169.254/",
                    "http://localhost/","https://user:pass@example.org/","https://example.org:8443/",
                    "https://example.org/news/%2e%2e/private","https://instagram.com/company/"]:
            with self.subTest(url=url),self.assertRaises(ValueError):
                canonical(url)

    def test_mixed_public_private_dns_rejected(self):
        addresses=[(2,1,6,"",("93.184.216.34",443)),(2,1,6,"",("127.0.0.1",443))]
        with patch("socket.getaddrinfo",return_value=addresses),self.assertRaises(ValueError):
            public_addresses("example.org",443)

    def test_redirect_cannot_leave_admitted_section(self):
        calls=[]
        def transport(url, limit):
            calls.append(url)
            if url.endswith("robots.txt"):
                return Response(404,b"",{})
            return Response(302,b"",{"location":"https://other.example.org/news/"})
        crawler=Crawler(self.store,transport,delay=0)
        result=crawler.run(crawler.submit(self.source()))
        self.assertEqual(result["status"],"completed_with_gaps")
        self.assertEqual(len(calls),2)
        self.assertEqual(self.store.coverage()["documents"],0)

    def test_robots_disallow_prevents_page_fetch(self):
        calls=[]
        def transport(url,limit):
            calls.append(url)
            return Response(200,b"User-agent: *\nDisallow: /news/",{})
        crawler=Crawler(self.store,transport,delay=0)
        crawler.run(crawler.submit(self.source()))
        self.assertEqual(len(calls),1)
        self.assertEqual(self.store.coverage()["documents"],0)

    def test_robots_failure_retains_pending_frontier(self):
        crawler=Crawler(self.store,lambda u,l:Response(503,b"",{}),delay=0)
        result=crawler.run(crawler.submit(self.source()))
        self.assertEqual(result["status"],"deferred")
        self.assertEqual(self.store.rows("SELECT status FROM frontier")[0]["status"],"pending")

    def test_oversized_page_not_indexed(self):
        def transport(url,limit):
            return Response(404,b"",{}) if url.endswith("robots.txt") else Response(200,b"x"*(limit+1),{"content-type":"text/html"})
        crawler=Crawler(self.store,transport,delay=0)
        crawler.run(crawler.submit(self.source()))
        self.assertEqual(self.store.coverage()["documents"],0)

    def test_budget_shared_between_concurrent_stores(self):
        source=self.source()
        job=Crawler(self.store).submit(source)
        def reserve(_):
            s=Store(self.path)
            try:
                s.reserve_fetch(job,"https://public.example.org","https://public.example.org/news/",daily=5)
                return True
            except ValueError:
                return False
            finally:
                s.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(reserve,range(12)))
        self.assertEqual(sum(results),5)

    def test_worker_lease_blocks_second_worker(self):
        import time
        crawler=Crawler(self.store)
        source=self.source()
        first,second=crawler.submit(source),crawler.submit(source)
        with self.store.db:
            self.store.db.execute("UPDATE jobs SET lease_until=? WHERE id=?",(time.time()+300,first))
        with self.assertRaises(ValueError):
            crawler.run(second)

    def test_completed_job_is_idempotent(self):
        result=run_demo(self.store)
        attempts=len(self.store.coverage()["attempts"])
        Crawler(self.store).run(result["id"])
        self.assertEqual(len(self.store.coverage()["attempts"]),attempts)

    def test_provider_previews_are_bounded_and_do_not_network(self):
        with patch("socket.getaddrinfo",side_effect=AssertionError("No network")):
            result=search_plan("Company","Frisco","award",advanced=True)
            social=social_plan("https://www.linkedin.com/company/company/","linkedin","2026-10-01T00:00:00Z")
        self.assertEqual(result["requests_sent"],0)
        self.assertEqual(result["estimated_credits"],4)
        self.assertFalse(social["input"]["scrapeComments"])
        with self.assertRaises(ValueError):
            social_plan("https://www.linkedin.com/in/person/","linkedin","2026-10-01T00:00:00Z")
        with self.assertRaises(ValueError):
            social_plan("https://instagram.com/company/","instagram","2026-10-01T00:00:00Z",0)

    def test_dashboard_escapes_content_and_blocks_csrf(self):
        self.store.ingest(None,"https://example.org/1","<script>alert(1)</script>","Public evidence")
        server=HTTPServer(("127.0.0.1",0),handler(self.path))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base="http://127.0.0.1:"+str(server.server_port)
        try:
            with urlopen(base) as r:
                body=r.read().decode()
                self.assertIn("&lt;script&gt;",body)
                self.assertIn("frame-ancestors",r.headers["Content-Security-Policy"])
            req=Request(base+"/qualify",data=b"lead_id=1",headers={"Content-Type":"application/x-www-form-urlencoded"})
            with self.assertRaises(HTTPError) as exc:
                urlopen(req)
            self.assertEqual(exc.exception.code,403)
            req=Request(base,headers={"Host":"attacker.example"})
            with self.assertRaises(HTTPError) as exc:
                urlopen(req)
            self.assertEqual(exc.exception.code,403)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__=="__main__":
    unittest.main()
