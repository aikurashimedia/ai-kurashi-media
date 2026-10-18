import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import bot

class PipelineTests(unittest.TestCase):
    def test_layout_and_identical_final(self):
        p={'slides':[{'title':'暮らしを便利にするヒント','body':'あ'*180}]*3,'caption':'初心者に向けたAI活用のヒントです。確認しながら使いましょう。今日の暮らしに役立ててください。'}
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            bot.render(bot.validate(p),folder)
            self.assertEqual(len(list(folder.glob('*.jpg'))),4)
            self.assertEqual((folder/'4.jpg').read_bytes(),(bot.ROOT/'assets/intro.jpg').read_bytes())
    def test_reject_invalid_count(self):
        with self.assertRaises(bot.SafeError):bot.validate({'slides':[],'caption':'a'*100})
    def test_reject_unverified_claim(self):
        with self.assertRaises(bot.SafeError):bot.validate({'slides':[{'title':'完全無料','body':'あ'}]*3,'caption':'a'*100})
    def test_uncertain_never_reposts(self):
        with tempfile.TemporaryDirectory() as t:
            state=Path(t)/'posts.json';state.write_text(json.dumps({'2026-10-18':{'status':'uncertain'}}))
            with patch.object(bot,'STATE',state),patch.dict(bot.CONFIG,enabled=True),patch.object(bot,'Meta') as meta:
                with self.assertRaises(bot.SafeError):bot.publish('2026-10-18')
                meta.assert_not_called()
    def test_wrong_account_stops(self):
        with patch.dict(bot.os.environ,{'META_ACCESS_TOKEN':'dummy','IG_USER_ID':'123'}):
            m=bot.Meta()
            with patch.object(m,'call',return_value={'username':'other'}):
                with self.assertRaises(bot.SafeError):m.verify()
    def test_published_skips(self):
        with tempfile.TemporaryDirectory() as t:
            state=Path(t)/'posts.json';state.write_text(json.dumps({'2026-10-18':{'status':'published'}}))
            with patch.object(bot,'STATE',state),patch.dict(bot.CONFIG,enabled=True),patch.object(bot,'Meta') as meta:
                bot.publish('2026-10-18');meta.assert_not_called()

if __name__=='__main__':unittest.main()
