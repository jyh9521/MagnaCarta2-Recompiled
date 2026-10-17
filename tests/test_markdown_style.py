import unittest
from pathlib import Path
from unittest.mock import patch
from tools.validators.validate_markdown_style import audit, main


class MarkdownStyleTests(unittest.TestCase):
    def test_objective(self): self.assertEqual(audit('原版输入保持只读；未验证完整播放。'), [])
    def test_chinese(self): self.assertEqual(len(audit('用户提供。我们测试。你的输入。')), 3)
    def test_english(self): self.assertEqual(len(audit('You provide your input; we record our result.')), 4)
    def test_english_discourse_role(self): self.assertEqual(len(audit('User-supplied input for users.')), 2)
    def test_inline_identifiers(self): self.assertEqual(audit('原参数 `user.full64<=3` 和 `r3(user)`。'), [])
    def test_fenced_code(self): self.assertEqual(audit('```text\nyou 用户\n```\n原输入。'), [])
    def test_tilde_fence(self): self.assertEqual(audit('~~~~\nwe\n~~~\nyou\n~~~~\n原输入。'), [])
    def test_indented_code(self): self.assertEqual(audit('    you\n\tour\n'), [])
    def test_url(self): self.assertEqual(audit('[API](https://example.test/users/you)'), [])
    def test_object_not_person(self): self.assertEqual(audit('其他字段与其偏移保持不变。'), [])
    def test_line_number(self): self.assertEqual(audit('原输入。\n用户。')[0]['line'], 2)
    def test_multitick_identifier(self): self.assertEqual(audit('``user`your``'), [])
    def test_root_and_empty_inventory_fail_closed(self):
        root = Path.cwd().resolve()
        with patch('tools.validators.validate_markdown_style.subprocess.check_output', return_value=str(root/'other')):
            with self.assertRaises(ValueError): main(['--root', str(root)])
        with patch('tools.validators.validate_markdown_style.subprocess.check_output', side_effect=[str(root), b'']):
            with self.assertRaises(ValueError): main(['--root', str(root)])


if __name__ == '__main__': unittest.main()
