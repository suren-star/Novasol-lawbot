import unittest
from unittest.mock import Mock
from bot import Bot, connect, parse_page, telegram_format


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(':memory:')
        self.bot = Bot.__new__(Bot)
        self.bot.db, self.bot.admin = self.db, 42
        self.bot.channel = '@novasol_official'
        self.bot.api, self.bot.send = Mock(), Mock()
        self.db.execute("INSERT INTO users VALUES(7,'ru')")
        self.db.execute("INSERT INTO drafts(fingerprint,hy,ru) VALUES('x','հայ','рус')")
        self.db.commit()

    def callback(self, user, action='approve'):
        self.bot.update({'callback_query': {'id':'q', 'from':{'id':user}, 'data':action+':1'}})

    def test_stranger_cannot_approve(self):
        self.callback(7)
        self.assertEqual(self.db.execute('SELECT status FROM drafts').fetchone()[0], 'pending')
        self.assertEqual(self.db.execute('SELECT count(*) FROM channel_deliveries').fetchone()[0], 0)

    def test_approval_is_idempotent(self):
        self.callback(42)
        self.callback(42)
        self.assertEqual(self.db.execute('SELECT count(*) FROM channel_deliveries').fetchone()[0], 1)

    def test_rejection_blocks_later_approval(self):
        self.callback(42, 'reject')
        self.callback(42)
        self.assertEqual(self.db.execute('SELECT count(*) FROM channel_deliveries').fetchone()[0], 0)

    def test_no_delivery_before_approval(self):
        self.bot.deliver()
        self.bot.send.assert_not_called()

    def test_public_commands_are_ignored(self):
        self.bot.update({'message':{'chat':{'id':7,'type':'private'},'from':{'id':7},'text':'/start'}})
        self.bot.send.assert_not_called()

    def test_channel_receives_only_armenian_after_approval(self):
        self.callback(42)
        self.bot.deliver()
        self.bot.deliver()
        self.bot.send.assert_called_once_with('@novasol_official', 'հայ')

    def test_missing_channel_blocks_approval(self):
        self.bot.channel = ''
        self.callback(42)
        self.assertEqual(self.db.execute('SELECT status FROM drafts').fetchone()[0], 'pending')

    def test_old_subscriber_deliveries_are_not_sent(self):
        self.db.execute("INSERT INTO deliveries VALUES(1,7,'queued')")
        self.bot.deliver()
        self.bot.send.assert_not_called()

    def test_parser_excludes_scripts(self):
        p = parse_page('<script>bad</script><a href="/hy/acts/1">Act</a>')
        self.assertEqual(p.text, ['Act'])
        self.assertEqual(p.links, [('/hy/acts/1','Act')])

    def test_sections_are_separated_and_bold_with_hidden_source_link(self):
        url='https://www.arlis.am/releases/files/6137/abc'
        text,entities=telegram_format('Ի՞նչ է փոխվել. Առաջին բաժին։ ՈՒմ է վերաբերում. Երկրորդ բաժին։ Ե՞րբ և ի՞նչ անել. Երրորդ բաժին։\n\nԱղբյուր՝\n'+url)
        self.assertIn('Ի՞նչ է փոխվել\nԱռաջին բաժին։\n\nՈ՞ւմ է վերաբերում\n',text)
        self.assertNotIn(url,text)
        self.assertNotIn('Աղբյուր՝',text)
        self.assertTrue(text.endswith('Կարդալ փաստաթուղթը'))
        self.assertEqual([e['type'] for e in entities],['bold','bold','bold','text_link'])
        self.assertEqual(entities[-1]['url'],url)

    def test_entity_offsets_use_utf16_and_do_not_parse_generated_markup(self):
        text,entities=telegram_format('📌 <b>տեքստ</b>\n\nԻ՞նչ է փոխվել\nԱկտ։')
        self.assertIn('<b>տեքստ</b>',text)
        encoded=text.encode('utf-16-le')
        entity=entities[0]
        self.assertEqual(encoded[entity['offset']*2:(entity['offset']+entity['length'])*2].decode('utf-16-le'),'Ի՞նչ է փոխվել')

    def test_send_passes_telegram_entities_and_keeps_preview_disabled(self):
        url='https://www.arlis.am/hy/acts/123/latest'
        Bot.send(self.bot,42,'Ի՞նչ է փոխվել\nՏեքստ։\n\n'+url)
        name=self.bot.api.call_args.args[0]
        payload=self.bot.api.call_args.kwargs
        self.assertEqual(name,'sendMessage')
        self.assertNotIn(url,payload['text'])
        self.assertEqual(payload['entities'][-1]['type'],'text_link')
        self.assertEqual(payload['link_preview_options'],{'is_disabled':True})


if __name__ == '__main__':
    unittest.main()
