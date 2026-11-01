import unittest
from arlis_source import recent_cards, document, evidence, act_url, SourceError


class ArlisTests(unittest.TestCase):
    def test_latest_links_and_shortcuts(self):
        html = '<a href="/hy/acts/1/latest">Old code shortcut</a><div class="act-card__title"><a href="/hy/acts/42/latest"><span>New act</span></a></div>'
        self.assertEqual(recent_cards(html), {'https://www.arlis.am/hy/acts/42/latest':'New act'})

    def test_missing_results_is_error(self):
        with self.assertRaises(SourceError):
            recent_cards('<html>Security page</html>')

    def test_external_url_rejected(self):
        with self.assertRaises(SourceError):
            act_url('https://example.com/hy/acts/1/latest')

    def page(self, text, extra=''):
        return '<title>Act</title><script>ignore me</script><nav>menu</nav><div id="act_body"><p>'+text+'</p></div>'+extra

    def test_body_omits_navigation(self):
        item = document(self.page('Legal text. '*30), '/hy/acts/2')
        self.assertNotIn('menu', item['text'])
        self.assertNotIn('ignore me', item['text'])

    def test_history_pairs_not_mistaken_for_revisions(self):
        extra = '<div class="nested-tab-container">Փոփոխող ակտ<div data-request-url="/hy/acts/1/compare/2"></div></div>'
        item = document(self.page('Legal text. '*30,extra), '/hy/acts/2')
        self.assertEqual(item['revision_pairs'], [])

    def test_explicit_pair_and_diff(self):
        extra = '<div class="nested-tab-container">Փոփոխություններ է կատարել հետևյալ ակտերում<div data-request-url="/hy/acts/1/compare/2"></div></div>'
        pages = {'https://www.arlis.am/hy/acts/3':self.page('Amendment. '*30,extra),
                 'https://www.arlis.am/hy/acts/1':self.page('Old wording. '*30),
                 'https://www.arlis.am/hy/acts/2':self.page('New wording. '*30)}
        item = evidence('https://www.arlis.am/hy/acts/3', loader=pages.__getitem__)
        self.assertEqual(len(item['comparisons']),1)
        change = item['comparisons'][0]['changes'][0]
        self.assertIn('Old wording',change['before'][0])
        self.assertIn('New wording',change['after'][0])


if __name__ == '__main__':
    unittest.main()
