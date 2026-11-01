import unittest
from unittest.mock import Mock
from bot import Bot, connect, parse_page


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


if __name__ == '__main__':
    unittest.main()
