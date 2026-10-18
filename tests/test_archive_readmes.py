"""Public archival entry points remain consistent across README languages."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ArchiveReadmeTests(unittest.TestCase):
    def test_language_navigation(self):
        names = ('README.md', 'README.en.md', 'README.ja.md')
        for name in names:
            text = (ROOT / name).read_text(encoding='utf-8')
            for other in names:
                if other != name:
                    self.assertIn('](' + other + ')', text)

    def test_local_links_resolve(self):
        for name in ('README.md', 'README.en.md', 'README.ja.md',
                     'docs/NATIVE_RECOMPILATION_ARCHIVE_2026-10-18.md'):
            path = ROOT / name
            for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                if '://' not in target:
                    self.assertTrue((path.parent / target.split('#')[0]).is_file(), (name, target))

    def test_suspension_and_xenia_in_every_readme(self):
        for name, phrase in [('README.md', '无限期暂停'),
                             ('README.en.md', 'suspended indefinitely'),
                             ('README.ja.md', '無期限に休止')]:
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertIn(phrase, text)
            self.assertIn('2026-10-18', text)
            self.assertIn('Xenia', text)

    def test_all_historical_stages_remain_indexed(self):
        text = (ROOT / 'docs/STATUS.md').read_text(encoding='utf-8')
        for phase in range(1, 37):
            self.assertRegex(text, r'(?m)^\| ' + str(phase) + r' \|')
