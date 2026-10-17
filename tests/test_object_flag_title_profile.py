import unittest
from unittest.mock import patch
from tools.research import probe_title_entry as p
class ObjectFlagTitleProfileTests(unittest.TestCase):
 def test_profile_exact(self):
  with patch.object(p,'OBJECT_FLAG_GENERATED_TREE','fixture-newtree',create=True):self.assertEqual(p.validate_title_profile({'tree_sha256':'fixture-newtree'}),'object-flag-leaf-8233D3D8')
 def test_prior_profile_remains(self):self.assertEqual(p.validate_title_profile({'tree_sha256':p.BYTE_FLAG_GENERATED_TREE}),'byte-flag-leaf-82E078C0')
 def test_unknown_tree_rejected(self):
  with self.assertRaises(ValueError):p.validate_title_profile({'tree_sha256':'unverified-tree'})
 def test_capture_new_original_profile(self):p.validate_capture_profile('object-flag-leaf-8233D3D8',True,True)
 def test_capture_unknown_rejected(self):
  with self.assertRaises(ValueError):p.validate_capture_profile('unknown',True,True)
 def test_fp_strict(self):p.validate_fp_contract('object-flag-leaf-8233D3D8',{'floating_point_contract':'strict'},[{'command':['/fp:strict']}])
 def test_fp_missing_or_mixed_rejected(self):
  for inputs,records in [({},[]),({'floating_point_contract':'strict'},[]),({'floating_point_contract':'strict'},[{'command':['/fp:fast']}]),({'floating_point_contract':'strict'},[{'command':['/fp:strict','/fp:fast']}]),({'floating_point_contract':'strict'},[{'command':['/fp:precise']}])]:
   with self.subTest(inputs=inputs,records=records):
    with self.assertRaises(ValueError):p.validate_fp_contract('object-flag-leaf-8233D3D8',inputs,records)
 def test_old_fp_profile_preserved(self):p.validate_fp_contract('extended-native-event-trace-rebuild',{},[])
