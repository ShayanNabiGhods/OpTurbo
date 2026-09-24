"""Tests for dependency-free duct calculations."""

import unittest

from opturbo.models import default_parsec_variables
from opturbo.parsec import nested_parameters, profile, validate_profile


class ParsecTests(unittest.TestCase):
    def test_default_profile_is_valid(self):
        parameters = nested_parameters(default_parsec_variables())
        validate_profile(parameters)
        x, upper, lower = profile(parameters, 50)
        self.assertEqual(len(x), 50)
        self.assertTrue(all(a > b for a, b in zip(upper[1:-1], lower[1:-1])))

    def test_bad_crest_location_is_rejected(self):
        parameters = nested_parameters(default_parsec_variables())
        parameters["upper"]["crest_location"] = 1.2
        with self.assertRaises(ValueError):
            validate_profile(parameters)


if __name__ == "__main__":
    unittest.main()

