"""Check that manual help links target named destinations in the bundled PDF."""

import json
import unittest
from urllib.parse import urlsplit
from unittest.mock import patch

from opturbo.gui import pdf_help


class PdfHelpTests(unittest.TestCase):
    def test_manual_destination_opens_existing_file_at_named_destination(self):
        destination = "mesh-settings"
        manual = pdf_help.DOCS_ROOT / "manual.pdf"
        expected_url = f"{manual.resolve().as_uri()}#nameddest={destination}"

        parsed = urlsplit(expected_url)
        self.assertEqual(parsed.scheme, "file")
        self.assertEqual(parsed.fragment, "nameddest=mesh-settings")
        self.assertTrue(manual.is_file())

        index = json.loads((pdf_help.DOCS_ROOT / "manual_help_index.json").read_text())
        self.assertIn(destination, index["manual_destinations"])

        with patch.object(pdf_help, "_edge_pdf_executable", return_value=None), \
             patch.object(pdf_help.webbrowser, "open_new_tab", return_value=True) as open_pdf:
            self.assertTrue(pdf_help._open_pdf_destination(manual, destination))
        open_pdf.assert_called_once_with(expected_url)


if __name__ == "__main__":
    unittest.main()
