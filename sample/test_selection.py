import unittest
from dataclasses import replace
from itertools import permutations
from demo import Candidate, select, examples, INCLUDE, OTHER, NO_REGION, INCOMPLETE, NO_PART


def row(reference, part, **kwargs):
    return Candidate("Target", 2022, "Relay", reference, part, **kwargs)


class SelectionTests(unittest.TestCase):
    def test_complete_set_beats_preferred_engine(self):
        result = select([row("A", "1"), row("B", "1", engine="2.0"),
                         row("B", "2", engine="2.0")])
        self.assertEqual([r.decision for r in result], [OTHER, INCLUDE, INCLUDE])

    def test_equal_size_different_sets_require_review(self):
        result = select([row("A", "1"), row("A", "2"), row("B", "1"), row("B", "3")])
        self.assertTrue(all(r.decision == INCOMPLETE for r in result))

    def test_null_region_does_not_affect_union_or_blank_part_guard(self):
        result = select([row("A", "1"), row("B", "2", region=None), row("B", None, region=None)])
        self.assertEqual([r.decision for r in result], [INCLUDE, NO_REGION, NO_REGION])

    def test_blank_part_fails_entire_eligible_group(self):
        for value in (None, "", "   "):
            result = select([row("A", "1"), row("B", value)])
            self.assertTrue(all(r.decision == NO_PART for r in result))

    def test_all_winner_details_survive(self):
        result = select(examples())
        included = [r for r in result if r.decision == INCLUDE]
        self.assertEqual(len(included), 4)
        self.assertEqual({r.position for r in included if r.part == "DEMO-001"}, {"Front", "Rear"})

    def test_engine_categories_before_row_count(self):
        rows = [row("Blank", "1"), row("Specified", "1", engine="2.0"),
                row("Mixed", "1"), row("Mixed", "1", engine="2.0")]
        self.assertEqual([r.reference for r in select(rows) if r.decision == INCLUDE], ["Blank"])
        self.assertEqual([r.reference for r in select(rows[1:]) if r.decision == INCLUDE], ["Specified"])

    def test_row_count_then_alphabetical(self):
        rows = [row("A", "1"), row("B", "1"), row("B", "1", position="Rear")]
        self.assertEqual(sum(r.decision == INCLUDE and r.reference == "B" for r in select(rows)), 2)
        self.assertEqual(select(rows[:2])[0].decision, INCLUDE)

    def test_order_independence(self):
        rows = [row("A", "1"), row("B", "1"), row("B", "2")]
        for variant in permutations(rows):
            self.assertEqual({r.reference for r in select(variant) if r.decision == INCLUDE}, {"B"})

    def test_group_isolation(self):
        rows = [row("A", "1"), replace(row("B", "2"), year=2023),
                replace(row("C", "3"), target="Other"), replace(row("D", "4"), description="Switch")]
        self.assertTrue(all(r.decision == INCLUDE for r in select(rows)))

    def test_empty_and_ineligible_only(self):
        self.assertEqual(select([]), [])
        self.assertEqual(select([row("A", "1", region=None)])[0].decision, NO_REGION)


if __name__ == "__main__":
    unittest.main()
