"""Check that the app's single Help action opens the bundled manual PDF."""

import unittest
from unittest.mock import patch

from opturbo.gui import pdf_help


class PdfHelpTests(unittest.TestCase):
    def test_manual_guide_opens_existing_pdf_file(self):
        manual = pdf_help.DOCS_ROOT / "manual.pdf"
        self.assertTrue(manual.is_file())

        with patch.object(pdf_help.webbrowser, "open_new_tab", return_value=True) as open_pdf:
            pdf_help.open_guide("manual.pdf")

        open_pdf.assert_called_once_with(manual.resolve().as_uri())


if __name__ == "__main__":
    unittest.main()
