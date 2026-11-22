import unittest
from mus import Constraint, minimal_conflicts, satisfiable


def c(i, kind, field="f", value=None):
    return Constraint(i, kind, field, value)


class MusTest(unittest.TestCase):
    def test_min_max_conflict(self):
        items = [c("min", "min_chars", value=100), c("max", "max_chars", value=50)]
        self.assertFalse(satisfiable(items))
        self.assertEqual([tuple(items)], minimal_conflicts(items))

    def test_required_forbidden_empty(self):
        items = [c("r", "required"), c("e", "forbidden_empty")]
        self.assertEqual([tuple(items)], minimal_conflicts(items))

    def test_include_avoid(self):
        items = [c("i", "must_include", value="A"), c("a", "must_avoid", value="A")]
        self.assertEqual([tuple(items)], minimal_conflicts(items))

    def test_satisfiable(self):
        items = [c("min", "min_chars", value=10), c("max", "max_chars", value=20)]
        self.assertTrue(satisfiable(items))
        self.assertEqual([], minimal_conflicts(items))

    def test_superset_not_reported(self):
        items = [c("min", "min_chars", value=100), c("max", "max_chars", value=50), c("r", "required")]
        mus = minimal_conflicts(items)
        self.assertEqual(1, len(mus))
        self.assertEqual(2, len(mus[0]))

    def test_two_independent_conflicts(self):
        items = [
            c("min", "min_chars", field="a", value=100),
            c("max", "max_chars", field="a", value=50),
            c("i", "must_include", field="b", value="X"),
            c("x", "must_avoid", field="b", value="X"),
        ]
        self.assertEqual(2, len(minimal_conflicts(items)))

    def test_single_constraints_satisfiable(self):
        for item in (c("r", "required"), c("max", "max_chars", value=0), c("i", "must_include", value="A")):
            self.assertTrue(satisfiable([item]))

    def test_empty(self):
        self.assertTrue(satisfiable([]))
        self.assertEqual([], minimal_conflicts([]))


if __name__ == "__main__":
    unittest.main()
