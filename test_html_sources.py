import unittest
from html_sources import ledger, capture, SourceError

URL = 'https://www.arlis.am/hy/acts/233019/latest'


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.db = ledger(':memory:')
        self.addCleanup(self.db.close)

    def reader(self,url):
        return dict(text='Armenian legal body',comparison_complete=True,url=url)

    def test_baseline_then_changed_snapshot(self):
        with self.assertRaises(SourceError):
            capture(self.db,[URL],reader=self.reader)
        self.assertEqual(capture(self.db,[URL],True,self.reader),1)
        self.assertEqual(capture(self.db,[URL],reader=self.reader),0)
        self.assertEqual(capture(self.db,[URL],reader=lambda u:dict(self.reader(u),text='changed')),1)
        self.assertEqual(self.db.execute('SELECT status FROM html_versions ORDER BY rowid').fetchall(),[('baseline',),('pending_review',)])
        with self.assertRaises(SourceError):
            capture(self.db,[URL],True,self.reader)

    def test_incomplete_evidence_is_not_committed(self):
        with self.assertRaises(SourceError):
            capture(self.db,[URL],True,lambda u:dict(self.reader(u),comparison_complete=False))
        self.assertEqual(self.db.execute('SELECT count(*) FROM html_versions').fetchone()[0],0)

    def test_empty_discovery_cannot_initialize_baseline(self):
        with self.assertRaises(SourceError):
            capture(self.db,[],True,self.reader)
        self.assertIsNone(self.db.execute('SELECT * FROM html_settings').fetchone())


if __name__ == '__main__':
    unittest.main()
