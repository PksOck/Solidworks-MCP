import unittest

from jsonschema import Draft7Validator

from solidworks_mcp.validation import ArgumentError, validate_arguments

SCHEMA = {
    "type": "object",
    "properties": {
        "file_path": {"type": "string"},
        "depth": {"type": "number", "minimum": 0},
        "unit": {"type": "string", "enum": ["mm", "cm", "m", "inch"]},
        "points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
    },
    "required": ["file_path"],
}
OPEN_SCHEMA = dict(SCHEMA, additionalProperties=True)


def check(arguments, schema=SCHEMA):
    return validate_arguments(schema, Draft7Validator(schema), arguments)


class ValidateArgumentsTests(unittest.TestCase):
    def test_valid_arguments_pass_unchanged(self):
        self.assertEqual({"file_path": "a", "depth": 2}, check({"file_path": "a", "depth": 2}))

    def test_top_level_none_values_are_dropped(self):
        self.assertEqual({"file_path": "a"}, check({"file_path": "a", "unit": None}))

    def test_unknown_key_suggests_the_closest_name(self):
        with self.assertRaises(ArgumentError) as caught:
            check({"filepath": "a"})
        self.assertEqual("filepath", caught.exception.argument)
        self.assertIn("Did you mean 'file_path'?", str(caught.exception))

    def test_unknown_key_without_close_match_lists_valid_names(self):
        with self.assertRaises(ArgumentError) as caught:
            check({"file_path": "a", "zzz": 1})
        self.assertIn("Valid arguments: depth, file_path, points, unit", str(caught.exception))

    def test_unknown_key_is_rejected_even_when_schema_allows_extra(self):
        with self.assertRaises(ArgumentError):
            check({"file_path": "a", "dpeth": 1}, OPEN_SCHEMA)

    def test_missing_required_argument(self):
        with self.assertRaises(ArgumentError) as caught:
            check({"depth": 1})
        self.assertEqual("file_path", caught.exception.argument)
        self.assertIn("'file_path' is a required property", str(caught.exception))

    def test_wrong_type_names_the_path(self):
        with self.assertRaises(ArgumentError) as caught:
            check({"file_path": "a", "points": [[0, 0], [1, "x"]]})
        self.assertEqual("points[1][1]", caught.exception.argument)
        self.assertTrue(str(caught.exception).startswith("Invalid argument 'points[1][1]':"))

    def test_enum_suggests_the_closest_value(self):
        with self.assertRaises(ArgumentError) as caught:
            check({"file_path": "a", "unit": "inches"})
        self.assertIn("Did you mean 'inch'?", str(caught.exception))

    def test_constraint_violation(self):
        with self.assertRaises(ArgumentError) as caught:
            check({"file_path": "a", "depth": -1})
        self.assertEqual("depth", caught.exception.argument)

    def test_schema_without_properties_accepts_anything(self):
        schema = {"type": "object"}
        self.assertEqual({"x": 1}, validate_arguments(schema, Draft7Validator(schema), {"x": 1}))


if __name__ == "__main__":
    unittest.main()
