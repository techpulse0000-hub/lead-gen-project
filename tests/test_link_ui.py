import unittest
from urllib.parse import urlsplit, parse_qs
from html import unescape
import re

from leadintel.link_ui import preview_link, alternative_links


class LinkUITests(unittest.TestCase):
    def test_preview_shows_real_host_and_escapes_untrusted_title(self):
        html=preview_link('https://www.linkedin.com/jobs/view/123', '<img src=x onerror=alert(1)>')
        self.assertIn('www.linkedin.com',html)
        self.assertNotIn('<img',html)
        self.assertIn('&lt;img',html)
        self.assertIn("role='tooltip'",html)
        self.assertIn("class='source-icon'",html)
        self.assertIn("aria-label='Open source:",html)
        self.assertIn('https://www.linkedin.com/jobs/view/123',html)
        for url in ('javascript:alert(1)','http://127.0.0.1/','https://user:secret@example.com/'):
            self.assertNotIn('<a ',preview_link(url,'unsafe'))

    def test_reviewed_alternative_only_matches_exact_posting(self):
        source='https://www.monster.com/job-openings/survey-crew-chief-plano-tx--957dd924-aa66-4548-ae65-3a47adea77e0'
        html=alternative_links({'url':source+'?utm_source=test','title':'Survey Crew Chief'})
        self.assertIn('jobs.smartrecruiters.com/timmonsgroup1/744000130037672',html)
        self.assertIn('Current availability and browser access are not confirmed',html)
        other=alternative_links({'url':'https://www.monster.com/different-job','title':'Survey Crew Chief'})
        self.assertNotIn('smartrecruiters',other)
        self.assertIn('No manually matched replacement',other)

    def test_fallback_encodes_title_and_related_links_are_not_claimed_as_copies(self):
        item={'url':'https://example.com/job','title':'A&B "Crew" <Dallas>'}
        html=alternative_links(item,[item,{'url':'https://other.example/news','title':'Different event'}])
        self.assertIn('may describe different opportunities',html)
        self.assertIn('Search results are not verified alternatives',html)
        link=unescape(re.search("href='(https://www.google.com/search[^']+)'",html)[1])
        self.assertEqual(parse_qs(urlsplit(link).query)['q'],[item['title']])
        self.assertNotIn('<Dallas>',html)


if __name__ == '__main__':
    unittest.main()
