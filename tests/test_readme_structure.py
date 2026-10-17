"""Keep the project landing page separate from research chronology."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReadmeStructureTests(unittest.TestCase):
    def test_landing_page_stays_short(self):
        text = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertLessEqual(len(text.splitlines()), 80)
        self.assertEqual(len(re.findall(r'^# ', text, re.M)), 1)

    def test_progress_has_a_dedicated_entry(self):
        text = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('](docs/STATUS.md)', text)
        self.assertNotRegex(text, r'(?m)^#{1,6}\s+.*(?:阶段\s*\d|第[一二三四五六七八九十]+阶段)')

    def test_debug_details_stay_out_of_landing_page(self):
        text = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertNotRegex(text, r'\b[0-9A-Fa-f]{8,64}\b|\.xxx\b|local/analysis/')

    def test_document_links_resolve_inside_repository(self):
        documents = ['README.md', 'docs/STATUS.md', 'docs/history/README_2026-10-18.md']
        for name in documents:
            path = ROOT / name
            for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                if target.startswith(('https://', 'http://', '#')):
                    continue
                resolved = (path.parent / target.split('#', 1)[0]).resolve()
                with self.subTest(document=name, target=target):
                    self.assertTrue(resolved.is_relative_to(ROOT.resolve()))
                    self.assertTrue(resolved.is_file())

    def test_history_is_marked_as_historical(self):
        text = (ROOT / 'docs/history/README_2026-10-18.md').read_text(encoding='utf-8')
        self.assertIn('属于历史记录', text)
        self.assertIn('](../STATUS.md)', text)
