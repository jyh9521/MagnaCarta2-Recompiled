import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.maintenance import cleanup_workspace as c


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.a = self.root/'local/analysis/current/a.exe'; self.a.parent.mkdir(parents=True)
        self.a.write_bytes(b'original executable fixture')
        self.b = self.root/'local/analysis/old/b.exe'; self.b.parent.mkdir(parents=True)
        self.b.write_bytes(self.a.read_bytes())
        self.keep = ['local/analysis/current']; self.report = self.root/'report.json'

    def plan(self): return c.make_plan(self.root, self.keep, 1)

    def test_exact_duplicate(self):
        p = self.plan(); self.assertEqual(p['retired_files'], 1)
        self.assertEqual(p['groups'][0]['keeper'], 'local/analysis/current/a.exe')
        self.assertEqual(p['reclaim_bytes'], self.a.stat().st_size)

    def test_plan_readonly(self):
        before = (self.a.read_bytes(), self.b.read_bytes()); self.plan()
        self.assertEqual(before, (self.a.read_bytes(), self.b.read_bytes()))

    def test_access_time_not_content_identity(self):
        before = self.a.stat(); os.utime(self.a, ns=(before.st_atime_ns+1000000000, before.st_mtime_ns))
        self.assertEqual(c.identity(before), c.identity(self.a.stat()))

    def test_roundtrip_and_idempotent_restore(self):
        old = self.b.stat().st_mtime_ns; p = self.plan(); r = c.apply(p, self.report)
        self.assertFalse(self.b.exists()); self.assertTrue(self.a.exists())
        self.assertEqual(r['status'], 'completed'); self.assertEqual(r['freed_bytes'], len(self.a.read_bytes()))
        self.assertEqual(c.restore(r)['restored_files'], 1)
        self.assertEqual(self.b.read_bytes(), self.a.read_bytes()); self.assertEqual(self.b.stat().st_mtime_ns, old)
        self.assertEqual(c.restore(r)['restored_files'], 0)

    def test_unique_preserved(self):
        self.b.write_bytes(b'unique research'); self.assertEqual(self.plan()['retired_files'], 0)

    def test_retained_copy_pinned_for_future_cleanup(self):
        c.apply(self.plan(), self.report)
        fresh = self.root/'local/analysis/new/c.exe'; fresh.parent.mkdir(); fresh.write_bytes(self.a.read_bytes())
        future = c.make_plan(self.root, ['local/analysis/new'], 1)
        self.assertIn('local/analysis/current/a.exe', future['keep'])
        self.assertEqual(future['retired_files'], 0)

    def test_broken_registered_keeper_fails_closed(self):
        c.apply(self.plan(), self.report); self.a.write_bytes(b'changed keeper')
        with self.assertRaises(ValueError): self.plan()

    def test_same_size_not_same_content(self):
        self.b.write_bytes(b'x'*self.a.stat().st_size); self.assertEqual(self.plan()['retired_files'], 0)

    def test_both_protected(self):
        self.keep.append('local/analysis/old'); self.assertEqual(self.plan()['retired_files'], 0)

    def test_file_protection(self):
        p = c.make_plan(self.root, ['local/analysis/old/b.exe'], 1)
        self.assertEqual(p['groups'][0]['keeper'], 'local/analysis/old/b.exe')

    def test_no_retention(self):
        with self.assertRaises(ValueError): c.make_plan(self.root, [], 1)

    def test_protection_must_exist(self):
        with self.assertRaises(ValueError): c.make_plan(self.root, ['absent'], 1)

    def test_below_threshold(self):
        self.assertEqual(c.make_plan(self.root, self.keep)['retired_files'], 0)

    def test_original_iso_and_text_untouched(self):
        for name in ['disc.iso', 'failure.log', 'report.json', 'source.cpp', 'evidence.txt']:
            p = self.b.parent/name; p.write_bytes(self.a.read_bytes())
        self.assertEqual(self.plan()['retired_files'], 1)

    def test_outside_analysis_untouched(self):
        for rel in ['local/upstream/a.exe', 'dist/a.exe', '.git/a.exe']:
            p = self.root/rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(self.a.read_bytes())
        self.assertEqual(self.plan()['retired_files'], 1)

    def test_dotgit_nested_excluded(self):
        p = self.b.parent/'.git/data.exe'; p.parent.mkdir(); p.write_bytes(self.a.read_bytes())
        self.assertEqual(self.plan()['retired_files'], 1)

    def test_paths_rejected(self):
        for value in ['../a', '/a', 'C:/a', 'a\\b', 'a//b', 'a/./b', '', 'a/.git/b', 'a./b', 'a /b']:
            with self.subTest(path=value), self.assertRaises(ValueError): c.relative(value)

    def test_changed_target_preflight_no_deletion(self):
        p = self.plan(); self.b.write_bytes(b'changed')
        with self.assertRaises(ValueError): c.apply(p, self.report)
        self.assertTrue(self.b.exists()); self.assertFalse(self.report.exists())

    def test_changed_keeper_preflight(self):
        p = self.plan(); self.a.write_bytes(b'changed')
        with self.assertRaises(ValueError): c.apply(p, self.report)
        self.assertTrue(self.b.exists())

    def test_all_targets_preflight(self):
        extra = self.b.with_name('c.exe'); extra.write_bytes(self.a.read_bytes())
        p = self.plan(); extra.write_bytes(b'changed')
        with self.assertRaises(ValueError): c.apply(p, self.report)
        self.assertTrue(self.b.exists())

    def test_plan_cannot_delete_protected(self):
        p = self.plan(); p['keep'].append('local/analysis/old')
        with self.assertRaises(ValueError): c.apply(p, self.report)

    def test_plan_cannot_select_source(self):
        p = self.plan(); p['groups'][0]['retired'][0]['path'] = 'local/analysis/old/evidence.txt'
        with self.assertRaises(ValueError): c.apply(p, self.report)

    def test_plan_duplicate_path(self):
        p = self.plan(); p['groups'][0]['retired'].append(copy.deepcopy(p['groups'][0]['retired'][0]))
        with self.assertRaises(ValueError): c.apply(p, self.report)

    def test_plan_totals(self):
        p = self.plan(); p['reclaim_bytes'] += 1
        with self.assertRaises(ValueError): c.apply(p, self.report)

    def test_existing_report_rejected(self):
        self.report.write_text('original')
        with self.assertRaises(ValueError): c.apply(self.plan(), self.report)
        self.assertEqual(self.report.read_text(), 'original')

    def test_keeper_lost_restore_fails(self):
        r = c.apply(self.plan(), self.report); self.a.unlink()
        with self.assertRaises(ValueError): c.restore(r)
        self.assertFalse(self.b.exists())

    def test_restore_existing_changed_never_overwritten(self):
        r = c.apply(self.plan(), self.report); self.b.write_bytes(b'new research')
        with self.assertRaises(ValueError): c.restore(r)
        self.assertEqual(self.b.read_bytes(), b'new research')

    def test_bad_restore_set(self):
        r = c.apply(self.plan(), self.report); r['removed'].append('local/analysis/other.exe')
        with self.assertRaises(ValueError): c.restore(r)

    def test_selective_restore(self):
        extra = self.b.with_name('c.exe'); extra.write_bytes(self.a.read_bytes())
        r = c.apply(self.plan(), self.report)
        self.assertEqual(c.restore(r, ['local/analysis/old/b.exe'])['restored_files'], 1)
        self.assertTrue(self.b.exists()); self.assertFalse(extra.exists())
        self.assertEqual(c.restore(r)['restored_files'], 1)

    def test_invalid_restore_selection(self):
        r = c.apply(self.plan(), self.report)
        for selected in [[], ['../escape'], ['local/analysis/absent']]:
            with self.subTest(selected=selected), self.assertRaises(ValueError): c.restore(r, selected)

    def test_journal_precedes_unlink(self):
        original = Path.unlink
        def fail(path, *args, **kwargs):
            if path == self.b: raise OSError('fixture interruption')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', fail), self.assertRaises(OSError): c.apply(self.plan(), self.report)
        r = json.loads(self.report.read_text()); self.assertEqual(r['status'], 'failed')
        self.assertEqual(r['removed'], ['local/analysis/old/b.exe'])
        self.assertEqual(c.restore(r)['restored_files'], 0)

    def test_hardlink_excluded(self):
        p = self.b.with_name('hard.exe')
        try: os.link(self.b, p)
        except OSError: self.skipTest('hardlinks unavailable')
        self.assertEqual(self.plan()['retired_files'], 0)

    def test_symlink_excluded(self):
        p = self.b.with_name('link.exe')
        try: p.symlink_to(self.a)
        except OSError: self.skipTest('symlinks unavailable')
        self.assertEqual(self.plan()['retired_files'], 1)

    def test_report_atomic_and_not_overwritten_through_link(self):
        p = self.root/'record.json'; c.save(p, {'a': 1})
        self.assertEqual(json.loads(p.read_text()), {'a': 1})
        self.assertFalse(p.with_name(p.name+'.pending').exists())

    def test_cli_plan_apply_restore(self):
        policy = self.root/'policy.json'; policy.write_text(json.dumps({'keep': self.keep}))
        # Default threshold deliberately produces an empty real plan.
        p = self.root/'plan.json'; self.assertEqual(c.main(['plan','--root',str(self.root),'--policy',str(policy),'--output',str(p)]), 0)
        with self.assertRaises(ValueError): c.main(['plan','--root',str(self.root),'--policy',str(policy),'--output',str(p)])
        self.assertEqual(c.main(['apply','--plan',str(p),'--report',str(self.report)]), 0)
        self.assertEqual(c.main(['restore','--report',str(self.report)]), 0)


if __name__ == '__main__': unittest.main()
