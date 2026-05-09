from django.test import TestCase

from question_factory.services.variable_expander import (
    cardinality, iter_bindings, sample_bindings,
)


class VariableExpanderTests(TestCase):
    def test_cardinality_product(self):
        # 3 × 2 × 2 = 12
        schema = {
            "a": ["x", "y", "z"],
            "b": [["1", "2"], ["3", "4"]],
            "c": {"items": ["m", "n"]},
        }
        self.assertEqual(cardinality(schema), 12)

    def test_cardinality_empty_returns_zero(self):
        self.assertEqual(cardinality({}), 0)
        self.assertEqual(cardinality({"a": []}), 0)

    def test_iter_bindings_enumerates_all(self):
        schema = {"a": ["x", "y"], "b": ["m", "n"]}
        out = list(iter_bindings(schema))
        self.assertEqual(len(out), 4)
        keys = {(b["a"], b["b"]) for b in out}
        self.assertEqual(keys, {("x", "m"), ("x", "n"), ("y", "m"), ("y", "n")})

    def test_sample_bindings_deterministic_for_same_seed(self):
        schema = {"a": ["x", "y", "z"], "b": ["m", "n", "o"]}
        a = sample_bindings(schema, n=5, seed_token="t1")
        b = sample_bindings(schema, n=5, seed_token="t1")
        self.assertEqual(a, b)

    def test_sample_bindings_changes_with_seed(self):
        schema = {"a": ["x", "y", "z"], "b": ["m", "n", "o"]}
        a = sample_bindings(schema, n=5, seed_token="t1")
        b = sample_bindings(schema, n=5, seed_token="t2")
        self.assertNotEqual(a, b)

    def test_sample_bindings_returns_count(self):
        schema = {"a": ["x", "y", "z"]}
        out = sample_bindings(schema, n=10)
        self.assertEqual(len(out), 10)

    def test_sample_bindings_handles_tuples(self):
        schema = {"v": [["go", "went"], ["eat", "ate"]]}
        out = sample_bindings(schema, n=3, seed_token="t")
        for b in out:
            self.assertIn(b["v"], schema["v"])
