import os
from pathlib import Path
import subprocess
import tempfile
import struct
import unittest
from tools.research import input_probe_trace_report as p


class InputProbeTraceTests(unittest.TestCase):
    def make(self, streams):
        data = bytearray(p.FILE_BYTES)
        struct.pack_into('<QQQ', data, 0, p.MAGIC, 1, p.FILE_BYTES)
        for w, rows in enumerate(streams):
            offset = 24 + w * p.STREAM_BYTES
            struct.pack_into('<QQ', data, offset, len(rows), 0)
            for n, (seq, kind, gated) in enumerate(rows):
                p.EVENT.pack_into(data, offset + 16 + n * p.EVENT.size,
                                  seq, 0x1000, 0, w + 10, w + 1, 0, kind, gated, 1)
        return data

    def test_overlapping_same_object(self):
        report = p.read_trace(self.make([[(1, 2, 0), (4, 5, 0)], [(2, 2, 0), (3, 5, 0)]]))
        self.assertEqual(report['delegate_peak'], 2)
        self.assertEqual(len(report['overlap']), 1)
        self.assertEqual(report['unfinished'], [])

    def test_gate_and_incomplete(self):
        report = p.read_trace(self.make([[(1, 2, 1), (2, 5, 1)], [(3, 2, 1)]]))
        self.assertEqual(report['delegate_peak'], 1)
        self.assertEqual(report['unfinished'][0]['thread'], 11)

    def test_corrupt_identity_count_sequence_and_pair(self):
        original = self.make([[(1, 2, 0)], []])
        bad = bytearray(original); bad[0] = 0
        with self.assertRaises(ValueError): p.read_trace(bad)
        bad = bytearray(original); struct.pack_into('<Q', bad, 24, p.CAPACITY + 1)
        with self.assertRaises(ValueError): p.read_trace(bad)
        with self.assertRaises(ValueError): p.read_trace(original[:-1])
        with self.assertRaises(ValueError): p.read_trace(self.make([[(1, 5, 0)], []]))
        with self.assertRaises(ValueError): p.read_trace(self.make([[(1, 2, 0)], [(1, 2, 0)]]))

    def test_saturation_is_not_complete(self):
        data = self.make([[], []]); struct.pack_into('<Q', data, 32, 123)
        report = p.read_trace(data)
        self.assertTrue(report['saturated'])
        self.assertEqual(report['dropped'], 123)


@unittest.skipUnless(os.environ.get('MC2_INPUT_REFRESH_PROBE'), 'local SDK probe not configured')
class NativeInputProbeTraceTests(unittest.TestCase):
    def test_real_sdk_serialized_trace_and_exclusive_file(self):
        exe = str(Path(os.environ['MC2_INPUT_REFRESH_PROBE']).resolve(strict=True))
        with tempfile.TemporaryDirectory() as out:
            trace = Path(out) / 'events.bin'
            env = dict(os.environ, MC2_INPUT_PROBE_TRACE=str(trace))
            command = [exe, 'serialized', '10000', '8192']
            run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            raw = trace.read_bytes()
            report = p.read_trace(raw)
            self.assertEqual(report['events'], 120002)
            self.assertEqual(report['delegate_peak'], 1)
            self.assertEqual(report['dropped'], 0)
            self.assertEqual(report['unfinished'], [])
            self.assertEqual(report['counts']['shutdown_leave'], 1)
            run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 4)
            self.assertEqual(trace.read_bytes(), raw)
