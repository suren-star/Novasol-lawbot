import unittest
from arlis_source import SourceError
from pdf_sources import ledger,record_inventory
from wide_sources import release_sections,inventory,commit_inventory

URL='https://www.arlis.am/releases/files/1/abc'
NEW='https://www.arlis.am/releases/files/2/abc'
THIRD='https://www.arlis.am/releases/files/3/abc'
HTML=''.join(f'<a class="service-card" href="/hy/releases/{i}">Section {i}</a>' for i in (11,15,16,6))


class WideTests(unittest.TestCase):
    def setUp(self):
        self.db=ledger(':memory:')
        self.addCleanup(self.db.close)
        record_inventory(self.db,{15:{URL:'Existing'}},True)
        self.sections={11:'Laws',15:'Government',16:'Normative',6:'Central bank'}

    def records(self): return {11:{},15:{URL:'Existing'},16:{},6:{NEW:'Additional'}}

    def test_discovers_cards_and_ignores_unrelated_links(self):
        self.assertEqual(set(release_sections(HTML+'<a href="/hy/releases/99">other</a>')),{11,15,16,6})
        with self.assertRaises(SourceError): release_sections('<html>error</html>')

    def test_new_sections_are_baseline_then_detect_new_publications(self):
        report=commit_inventory(self.db,self.sections,self.records())
        self.assertEqual(report['additional_baseline_records'],1)
        self.assertEqual(report['new_records'],0)
        records=self.records(); records[6][THIRD]='Later'
        report=commit_inventory(self.db,self.sections,records)
        self.assertEqual(report['new_records'],1)
        self.assertEqual(self.db.execute('SELECT is_baseline FROM source_records WHERE url=?',(THIRD,)).fetchone()[0],0)

    def test_overlap_with_old_scope_still_detected_as_new(self):
        records=self.records(); records[15][NEW]='Same act'
        report=commit_inventory(self.db,self.sections,records)
        self.assertEqual(report['new_records'],1)
        self.assertEqual(report['additional_baseline_records'],0)

    def test_repeated_inventory_preserves_flags_and_review_status(self):
        self.db.execute("UPDATE source_records SET status='manual_review' WHERE url=?",(URL,)); self.db.commit()
        commit_inventory(self.db,self.sections,self.records())
        report=commit_inventory(self.db,self.sections,self.records())
        self.assertEqual(report['new_records']+report['additional_baseline_records'],0)
        self.assertEqual(self.db.execute('SELECT is_baseline,status FROM source_records WHERE url=?',(URL,)).fetchone(),(1,'manual_review'))

    def test_partial_results_do_not_commit(self):
        with self.assertRaises(SourceError): commit_inventory(self.db,self.sections,{15:{URL:'Existing'}})
        self.assertEqual(self.db.execute('SELECT count(*) FROM source_records').fetchone()[0],1)

    def test_failed_remote_category_is_reported(self):
        def file_loader(ident):
            if ident==6: raise SourceError('unavailable')
            return {}
        with self.assertRaises(SourceError): inventory(loader=lambda u:HTML,file_loader=file_loader)
        self.assertEqual(self.db.execute('SELECT count(*) FROM source_records').fetchone()[0],1)


if __name__=='__main__': unittest.main()
