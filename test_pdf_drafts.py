import os
import unittest
from unittest.mock import patch,Mock
from bot import Bot,connect,APIError
from pdf_sources import ledger,record_inventory,save_version
from pdf_drafts import plan,generate,retry_sample,notify_previews,DISCLAIMER


class DraftBridgeTests(unittest.TestCase):
    def setUp(self):
        self.sources = ledger(':memory:')
        self.db = connect(':memory:')
        self.addCleanup(self.sources.close)
        self.addCleanup(self.db.close)
        self.env = patch.dict(os.environ,{'TELEGRAM_BOT_TOKEN':'fake','ADMIN_CHAT_ID':'1',
                          'OPENAI_API_KEY':'fake','OPENAI_MODEL':'fake'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.bot = Bot(self.db)
        self.url = 'https://www.arlis.am/releases/files/1/abc'
        record_inventory(self.sources,{15:{self.url:'baseline'}},True)
        self.save(self.url)

    def save(self,url,status='extracted',text='source body'):
        save_version(self.sources,url,dict(sha256='abc',pages=1,text=text,status=status,
                                        uncertain_pages=[] if status=='extracted' else [1],official_links=[]))

    def add(self,n,status='extracted',text='source body'):
        url=f'https://www.arlis.am/releases/files/{n}/abc'
        record_inventory(self.sources,{15:{url:'New act'}})
        self.save(url,status,text)
        return url

    def summary(self,bot,row):
        return {'relevant':True,'hy':'Օրենսդրական ակտի ամփոփագիր։'}

    def test_baseline_and_manual_review_never_generated(self):
        self.add(2,'manual_review')
        self.assertEqual(plan(self.sources,self.db)['ready'],0)
        def forbidden(*args):
            raise AssertionError('Should not call AI')
        generate(self.sources,self.bot,forbidden)
        self.assertEqual(self.db.execute('SELECT count(*) FROM drafts').fetchone()[0],0)

    def test_draft_is_pending_cited_and_idempotent(self):
        url=self.add(2)
        generate(self.sources,self.bot,self.summary)
        row=self.db.execute('SELECT hy,status,notified FROM drafts').fetchone()
        self.assertIn(url,row[0])
        self.assertIn(DISCLAIMER,row[0])
        self.assertEqual(row[1:],('pending',0))
        generate(self.sources,self.bot,self.summary)
        self.assertEqual(self.db.execute('SELECT count(*) FROM drafts').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM channel_deliveries').fetchone()[0],0)

    def test_failed_paid_call_is_not_retried(self):
        self.add(2)
        calls=[]
        def fail(*args):
            calls.append(1)
            raise RuntimeError('service unavailable')
        with self.assertRaises(RuntimeError):
            generate(self.sources,self.bot,fail)
        generate(self.sources,self.bot,fail)
        self.assertEqual(len(calls),1)
        self.assertEqual(self.db.execute('SELECT status FROM pdf_generation').fetchone()[0],'review')

    def test_daily_cap_and_one_call_per_invocation(self):
        for n in range(2,6): self.add(n)
        for _ in range(3): generate(self.sources,self.bot,self.summary,day='2026-11-02')
        self.assertIn('Daily request limit',generate(self.sources,self.bot,self.summary,day='2026-11-02'))
        self.assertEqual(self.db.execute('SELECT count(*) FROM drafts').fetchone()[0],3)

    def test_oversize_is_not_silently_truncated(self):
        self.add(2,text='x'*60001)
        self.assertEqual(plan(self.sources,self.db)['oversize_or_empty'],1)
        self.assertIn('No eligible',generate(self.sources,self.bot,self.summary))

    def test_invalid_language_is_blocked(self):
        self.add(2)
        with self.assertRaises(ValueError):
            generate(self.sources,self.bot,lambda *args:dict(relevant=True,hy='English only'))
        self.assertEqual(self.db.execute('SELECT count(*) FROM drafts').fetchone()[0],0)

    def test_baseline_sample_cannot_be_published(self):
        generate(self.sources,self.bot,self.summary,preview=True)
        ident,status=self.db.execute('SELECT id,status FROM drafts').fetchone()
        self.assertEqual(status,'preview')
        self.assertEqual(self.sources.execute('SELECT is_baseline FROM source_records').fetchone()[0],1)
        self.assertEqual(plan(self.sources,self.db)['ready'],0)
        self.bot.api=Mock()
        self.bot.send=Mock()
        self.bot.notify()
        self.bot.send.assert_not_called()
        self.bot.update({'callback_query':{'id':'q','from':{'id':1},'data':f'approve:{ident}'}})
        self.assertEqual(self.db.execute('SELECT status FROM drafts').fetchone()[0],'preview')
        self.assertEqual(self.db.execute('SELECT count(*) FROM channel_deliveries').fetchone()[0],0)
        self.assertEqual(notify_previews(self.bot),1)
        args,kwargs=self.bot.send.call_args
        self.assertEqual(args[0],1)
        self.assertNotIn('reply_markup',kwargs)
        self.assertEqual(notify_previews(self.bot),0)

    def test_preview_deduplicates_and_shares_daily_cap(self):
        generate(self.sources,self.bot,self.summary,preview=True,day='2026-11-02')
        self.assertIn('No eligible',generate(self.sources,self.bot,self.summary,preview=True,day='2026-11-02'))
        for n in range(2,5): self.add(n)
        for _ in range(2): generate(self.sources,self.bot,self.summary,day='2026-11-02')
        self.assertIn('Daily request limit',generate(self.sources,self.bot,self.summary,day='2026-11-02'))

    def test_explicit_retry_keeps_source_and_does_not_repeat(self):
        def fail(*args): raise APIError('HTTP 429')
        with self.assertRaises(APIError):
            generate(self.sources,self.bot,fail,preview=True)
        seen=[]
        def summary(bot,row):
            seen.append(row[0])
            return self.summary(bot,row)
        self.assertIn('preview',retry_sample(self.sources,self.bot,summary))
        self.assertEqual(seen,[self.url])
        self.assertIn('already attempted',retry_sample(self.sources,self.bot,summary))
        self.assertEqual(len(seen),1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM pdf_generation').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT status FROM drafts').fetchone()[0],'preview')


if __name__ == '__main__':
    unittest.main()
