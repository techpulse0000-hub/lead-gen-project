import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.build_registry import ROOT, approved_profiles, build_payload, profile_identity, write_database
from tools.search_socials import filter_results, make_queries, reserve
from tools.verify_sources import validate_url


class IdentityTests(unittest.TestCase):
    def test_x_aliases_and_tracking_do_not_duplicate_accounts(self):
        self.assertEqual(profile_identity('https://twitter.com/KPostDFW?lang=en'), profile_identity('https://x.com/kpostdfw/'))

    def test_linkedin_locales_and_encoded_ampersand_match(self):
        self.assertEqual(profile_identity('https://tw.linkedin.com/company/kpost-roofing-%26-waterproofing'), profile_identity('https://www.linkedin.com/company/kpost-roofing-&-waterproofing'))

    def test_posts_people_and_spoofed_domains_are_not_company_accounts(self):
        for url in ['https://www.linkedin.com/in/someone', 'https://x.com/kpostdfw/status/123', 'https://www.instagram.com/p/abc', 'https://www.facebook.com/sharer.php?u=https://example.com', 'https://youtu.be/kQUsbxbXnuU', 'https://www.linkedin.com.evil.example/company/test', 'https://user:pass@x.com/kpostdfw']:
            with self.subTest(url=url):
                self.assertIsNone(profile_identity(url))

    def test_company_footer_partner_is_not_automatically_verified(self):
        check={'social_links':['https://www.facebook.com/PolkMechanical','https://www.facebook.com/buildtexasproud/']}
        accepted=approved_profiles('polk',check,{'polk':['https://www.facebook.com/PolkMechanical']})
        self.assertEqual(len(accepted),1)
        self.assertNotIn('buildtexasproud',accepted[0][0])

    def test_private_and_credential_urls_are_rejected_before_request(self):
        for url in ['http://127.0.0.1/', 'http://169.254.169.254/', 'http://localhost/', 'file:///etc/passwd', 'https://user:pass@example.com/', 'https://example.com:8443/']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url,resolve=False)

    def test_repeated_official_links_collapse_to_one_account(self):
        check={'social_links':['https://twitter.com/KPostDFW?lang=en','https://x.com/kpostdfw/']}
        accepted=approved_profiles('kpost',check,{'kpost':['https://x.com/kpostdfw']})
        self.assertEqual(len(accepted),1)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='registry-test-', dir=ROOT/'tests')
        self.path=Path(self.temp.name)/'registry.sqlite'
        self.payload=build_payload()
        write_database(self.payload,self.path)
        self.db=sqlite3.connect(self.path)
        self.db.execute('PRAGMA foreign_keys=ON')

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_curated_accounts_have_actual_official_link_evidence(self):
        checks={c['id']:c for c in self.payload['source_checks']}
        for p in self.payload['company_profiles']:
            if p['verification_status']=='official_site_linked':
                self.assertIn(p['original_url'],checks[p['company_id']]['social_links'])
                self.assertEqual(checks[p['company_id']]['access_status'],'retrieved')
        self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_required_platforms_have_actual_search_records_for_each_company(self):
        for c in self.payload['companies']:
            found={r[0] for r in self.db.execute('SELECT platform FROM search_checks WHERE company_id=?',(c['id'],))}
            self.assertTrue({'linkedin','instagram','x','indeed'} <= found)

    def test_rebuild_is_idempotent_and_preserves_usage_history(self):
        query=make_queries(self.db,['kpost'])[0]
        reserve(self.db,query,'2026-10-12T10:00:00+00:00')
        old=self.db.execute('SELECT COUNT(*) FROM company_profiles').fetchone()[0]
        write_database(self.payload,self.path)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM company_profiles').fetchone()[0],old)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM search_attempts').fetchone()[0],1)

    def test_queries_use_verified_handles_and_read_stored_companies(self):
        q=next(q for q in make_queries(self.db,['kpost']) if q['platform']=='x')
        self.assertIn('kpostdfw',q['query'])
        self.db.execute("INSERT INTO companies VALUES ('new_company','Example Contractor','https://example.com','construction','Dallas','research_prospect','{}')")
        self.db.commit()
        self.assertEqual(len(make_queries(self.db,['new_company'])),4)

    def test_daily_budget_includes_failed_and_reserved_requests(self):
        q=make_queries(self.db,['kpost'])[0]
        for _ in range(30):
            reserve(self.db,q,'2026-10-12T10:00:00+00:00')
        with self.assertRaisesRegex(ValueError,'budget exhausted'):
            reserve(self.db,q,'2026-10-12T11:00:00+00:00')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM search_attempts').fetchone()[0],30)

    def test_monthly_budget_blocks_a_new_day(self):
        self.db.executemany("INSERT INTO search_attempts(created_at,company_id,platform,query,status,estimated_cost_microusd) VALUES (?,'kpost','x','query','failed',8000)", [(f'2026-10-{1+i//30:02d}T10:00:00+00:00',) for i in range(900)])
        self.db.commit()
        with self.assertRaisesRegex(ValueError,'budget exhausted'):
            reserve(self.db,make_queries(self.db,['kpost'])[0],'2026-10-31T10:00:00+00:00')

    def test_search_hits_never_become_verified_facts_or_hiring_counts(self):
        item={'platform':'linkedin','domains':['linkedin.com']}
        response={'results':[{'url':'https://www.linkedin.com/posts/example_test','title':'Hiring 100','content':'We are growing'}, {'url':'https://www.linkedin.com/in/person'}, {'url':'https://linkedin.com.evil.example/post'}]}
        results=filter_results(response,item)
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]['status'],'unverified_index_candidate')
        self.assertIsNone(results[0]['worker_quantity'])
        self.assertIsNone(results[0]['event_date'])


class CommandTests(unittest.TestCase):
    def test_preview_needs_no_key_and_sends_no_requests(self):
        result=subprocess.run([sys.executable,str(ROOT/'tools/search_socials.py'),'--company','kpost','--limit','4'],capture_output=True,text=True,check=True)
        output=json.loads(result.stdout)
        self.assertEqual(output['requests_sent'],0)
        self.assertEqual(len(output['queries']),4)

    def test_missing_key_stops_execution_without_an_attempt(self):
        env=dict(os.environ)
        env.pop('TAVILY_API_KEY',None)
        db=sqlite3.connect(ROOT/'data/source_registry.sqlite')
        before=db.execute('SELECT COUNT(*) FROM search_attempts').fetchone()[0]
        result=subprocess.run([sys.executable,str(ROOT/'tools/search_socials.py'),'--execute'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('No requests were sent',result.stderr)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM search_attempts').fetchone()[0],before)
        db.close()


if __name__=='__main__':
    unittest.main()
