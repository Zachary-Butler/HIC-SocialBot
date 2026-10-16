"""Smoke tests: the CLI modules import and parse. Catches syntax errors in code the unit tests
don't exercise."""

import contextlib
import io
import unittest

from socialbot.__main__ import main


class CliTests(unittest.TestCase):
    def test_help_renders_every_subcommand(self):
        for argv in (["--help"], ["news", "--help"], ["news", "build", "--help"], ["news", "draft", "--help"],
                     ["news", "roundup", "--help"], ["news", "feeds", "--help"]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as cm:
                main(argv)
            self.assertEqual(cm.exception.code, 0, argv)
            self.assertIn("usage:", out.getvalue())
