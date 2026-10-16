import unittest
from tools.formats.summarize_ue3 import summarize


def fixture(paths, names=()):
    return dict(schema_version=1, summary=dict(class_histogram={}),
                packages=[dict(path=p) for p in paths],
                package_edges=[dict(source="synthetic.xxx", target_name=n, target_path=None) for n in names])


class SummaryTests(unittest.TestCase):
    def test_unique_cross_disc_candidate(self):
        result = summarize([fixture([], ["Core"]), fixture(["Core.xxx"])])
        self.assertEqual(result["cross_disc_candidates"][0][0]["other_disc_path"], "Core.xxx")

    def test_ambiguous_cross_disc_not_arbitrary(self):
        result = summarize([fixture([], ["Core"]), fixture(["a/Core.xxx", "b/Core.xxx"])])
        row = result["cross_disc_candidates"][0][0]
        self.assertIsNone(row["other_disc_path"])
        self.assertEqual(len(row["other_disc_candidates"]), 2)

    def test_missing_candidate(self):
        result = summarize([fixture([], ["Core"]), fixture([])])
        self.assertEqual(result["cross_disc_candidates"][0][0]["other_disc_candidates"], [])

    def test_bad_schema(self):
        with self.assertRaises(ValueError):
            summarize([dict(schema_version=999)])
