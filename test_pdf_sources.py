import unittest
from unittest.mock import patch, Mock
from pdf_sources import (ledger, record_inventory, scan, save_version,
                         extract_pending, extract_pdf, SourceError)

URL = 'https://www.arlis.am/releases/files/6136/ab19adba'
URL2 = 'https://www.arlis.am/releases/files/6137/abc123'


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = ledger(':memory:')
        self.addCleanup(self.db.close)

    def test_baseline_is_explicit_and_cannot_hide_later_records(self):
        with self.assertRaises(SourceError):
            record_inventory(self.db,{11:{URL:'first'}})
        record_inventory(self.db,{11:{URL:'first'}},baseline=True)
        with self.assertRaises(SourceError):
            record_inventory(self.db,{11:{URL2:'second'}},baseline=True)
        record_inventory(self.db,{11:{URL:'first',URL2:'second'}})
        self.assertEqual(self.db.execute('SELECT is_baseline FROM source_records ORDER BY url').fetchall(),[(1,),(0,)])

    def test_duplicate_across_sections_and_scans(self):
        self.assertEqual(record_inventory(self.db,{11:{URL:'one'},15:{URL:'one'}},True),1)
        self.assertEqual(record_inventory(self.db,{11:{URL:'one'}}),0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM source_sections').fetchone()[0],2)

    def test_failed_section_does_not_commit_partial_inventory(self):
        def loader(section):
            if section == 15:
                raise SourceError('unavailable')
            return {URL:'one'}
        with self.assertRaises(SourceError):
            scan(self.db,baseline=True,loader=loader)
        self.assertEqual(self.db.execute('SELECT count(*) FROM source_records').fetchone()[0],0)

    def test_invalid_url_rolls_back_entire_inventory(self):
        with self.assertRaises(SourceError):
            record_inventory(self.db,{11:{URL:'ok','https://example.com/file':'bad'}},True)
        self.assertEqual(self.db.execute('SELECT count(*) FROM source_records').fetchone()[0],0)

    def test_versions_deduplicate_content_and_preserve_changes(self):
        record_inventory(self.db,{11:{URL:'one'}},True)
        item = dict(sha256='a',pages=1,text='text',status='extracted',uncertain_pages=[],official_links=[])
        self.assertTrue(save_version(self.db,URL,item))
        self.assertFalse(save_version(self.db,URL,item))
        self.assertTrue(save_version(self.db,URL,dict(item,sha256='b',text='changed')))
        self.assertEqual(self.db.execute('SELECT count(*) FROM source_versions').fetchone()[0],2)

    def test_unreadable_source_remains_recorded_for_review(self):
        record_inventory(self.db,{11:{URL:'one'}},True)
        def fail(url):
            raise SourceError('failed')
        result = extract_pending(self.db,downloader=fail)
        self.assertEqual(result[0]['status'],'manual_review')
        self.assertEqual(self.db.execute('SELECT error_type FROM source_errors').fetchone()[0],'SourceError')
        self.assertEqual(extract_pending(self.db,downloader=fail),[])


class ExtractionTests(unittest.TestCase):
    def test_image_only_page_requires_review(self):
        page = Mock()
        page.extract_text.return_value = ''
        page.get.return_value = []
        reader = Mock(is_encrypted=False,pages=[page])
        with patch('pypdf.PdfReader',return_value=reader):
            result = extract_pdf(b'%PDF-fixture')
        self.assertEqual(result['status'],'manual_review')
        self.assertIn(1,result['uncertain_pages'])

    def test_readable_armenian_text_preserved(self):
        page = Mock()
        page.extract_text.return_value = 'Հայաստանի Հանրապետության օրենքի փոփոխություն։ ' * 10
        page.get.return_value = []
        reader = Mock(is_encrypted=False,pages=[page])
        with patch('pypdf.PdfReader',return_value=reader):
            result = extract_pdf(b'%PDF-fixture')
        self.assertEqual(result['status'],'extracted')
        self.assertIn('փոփոխություն',result['text'])


if __name__ == '__main__':
    unittest.main()
