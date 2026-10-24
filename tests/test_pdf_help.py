"""Check that manual help links use named PDF destinations over HTTP."""

import json
import unittest
from urllib.request import urlopen
from urllib.parse import urlsplit

from opturbo.gui import pdf_help


class PdfHelpTests(unittest.TestCase):
    def test_manual_destination_url_uses_loopback_http_and_named_destination(self):
        destination = "mesh-settings"
        url = pdf_help._docs_url("manual.pdf", destination)
        parsed = urlsplit(url)

        self.assertEqual(parsed.scheme, "http")
        self.assertEqual(parsed.hostname, "127.0.0.1")
        self.assertEqual(parsed.fragment, "nameddest=mesh-settings")

        index = json.loads((pdf_help.DOCS_ROOT / "manual_help_index.json").read_text())
        self.assertIn(destination, index["manual_destinations"])

        with urlopen(url.split("#", 1)[0]) as response:
            self.assertEqual(response.status, 200)
            self.assertTrue(response.read(4).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
