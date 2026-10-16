import unittest
from tools.research.compare_dependencies import cross_disc


def report(paths, edges=()):
    return dict(schema_version=1, packages=[dict(path=p, status="tables-validated") for p in paths],
                package_edges=[dict(source="source.xxx", target_name=name) for name in edges])


class DependencyTests(unittest.TestCase):
    def test_same_disc(self):
        r = cross_disc(report(["Core.xxx"], ["Core"]), report([]))
        self.assertEqual(r["counts"]["disc1:unique-same-disc-candidate"], 1)

    def test_cross_disc_candidate(self):
        r = cross_disc(report([], ["Other"]), report(["Other.xxx"]))
        self.assertEqual(r["counts"]["disc1:unique-other-disc-candidate"], 1)

    def test_ambiguous_is_not_resolved(self):
        r = cross_disc(report(["one/Core.xxx", "two/Core.xxx"], ["Core"]), report([]))
        self.assertEqual(r["counts"]["disc1:ambiguous-same-disc-candidates"], 1)

    def test_missing(self):
        r = cross_disc(report([], ["NotPresent"]), report([]))
        self.assertEqual(r["counts"]["disc1:no-inventoried-candidate"], 1)

    def test_casefold(self):
        r = cross_disc(report(["Core.xxx"], ["cOrE"]), report([]))
        self.assertEqual(r["counts"]["disc1:unique-same-disc-candidate"], 1)

    def test_reject_partial(self):
        d = report(["Core.xxx"]); d["packages"][0]["status"] = "summary-only"
        with self.assertRaises(ValueError):
            cross_disc(d, report([]))

    def test_reject_schema(self):
        with self.assertRaises(ValueError):
            cross_disc(dict(schema_version=2), report([]))

    def test_reject_malformed_rows(self):
        for invalid in ([], dict(schema_version=1, packages=[None], package_edges=[]),
                        dict(schema_version=1, packages=[], package_edges=[dict(source="x", target_name=1)])):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                cross_disc(invalid, report([]))
