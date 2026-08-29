import unittest

from support import import_package

import_package()

from web_design_radar.scoring import Candidate, score_candidate, select_candidates


def candidate(url, score, tags):
    return Candidate(
        site_url=url,
        source_url=f"https://www.awwwards.com/sites/{url.split('//')[1].split('.')[0]}",
        title=url,
        technology=score,
        industry=score,
        popularity=score,
        novelty=score,
        analyzability=score,
        tags=tags,
    )


class ScoringTest(unittest.TestCase):
    def test_weighted_score_uses_the_approved_five_dimensions(self):
        """Catches swapped or omitted selection weights."""
        item = Candidate(
            site_url="https://alpha.example",
            source_url="https://www.awwwards.com/sites/alpha",
            title="Alpha",
            technology=1.0,
            industry=0.8,
            popularity=0.5,
            novelty=0.4,
            analyzability=0.9,
            tags=("webgl", "energy"),
        )
        self.assertAlmostEqual(score_candidate(item), 0.78)

    def test_dimension_outside_unit_interval_is_rejected(self):
        """Catches unnormalized agent scores dominating selection."""
        with self.assertRaisesRegex(ValueError, "technology"):
            candidate("https://bad.example", 1.1, ("webgl",))

    def test_selection_is_exactly_two_unique_domains(self):
        """Catches www/path variants consuming both daily slots."""
        selected = select_candidates(
            [
                candidate("https://a.example", 1.0, ("webgl",)),
                candidate("https://www.a.example/work", 0.99, ("threejs",)),
                candidate("https://b.example", 0.9, ("gsap",)),
                candidate("https://c.example", 0.8, ("shader",)),
            ],
            previous_domains=set(),
            quota=2,
        )
        self.assertEqual([item.canonical_domain for item in selected], ["a.example", "b.example"])

    def test_second_slot_prefers_tag_diversity_within_ten_points(self):
        """Catches two near-identical examples crowding out a comparable diverse site."""
        selected = select_candidates(
            [
                candidate("https://a.example", 1.0, ("webgl",)),
                candidate("https://b.example", 0.95, ("webgl",)),
                candidate("https://c.example", 0.90, ("gsap",)),
            ],
            previous_domains=set(),
            quota=2,
        )
        self.assertEqual([item.canonical_domain for item in selected], ["a.example", "c.example"])


if __name__ == "__main__":
    unittest.main()
