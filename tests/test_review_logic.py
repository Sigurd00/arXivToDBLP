import unittest

from review_logic import generate_review_proposals


class FakeLookupService:
    def __init__(self):
        self.calls = []

    def lookup_many(self, arxiv_ids, original_keys):
        self.calls.append((list(arxiv_ids), list(original_keys)))
        out = []
        for arxiv_id, key in zip(arxiv_ids, original_keys):
            if not arxiv_id:
                out.append(None)
            else:
                out.append(
                    {
                        "type": "article",
                        "citation_key": key,
                        "fields": {
                            "title": "Replacement",
                            "year": "2026",
                            "author": "A. Author",
                        },
                    }
                )
        return out


class ReviewLogicTests(unittest.TestCase):
    def test_deduping_input_to_lookup_is_unique_per_record_extract(self):
        records = [
            {
                "type": "article",
                "citation_key": "k1",
                "fields": {"title": "Old1", "eprint": "arxiv:2401.12345"},
            },
            {
                "type": "article",
                "citation_key": "k2",
                "fields": {"title": "Old2", "eprint": "arxiv:2401.12345"},
            },
            {
                "type": "article",
                "citation_key": "k3",
                "fields": {"title": "Old3", "eprint": "arxiv:2402.99999"},
            },
        ]

        fake = FakeLookupService()
        proposals, changes = generate_review_proposals(records, lookup_service=fake)

        self.assertEqual(len(proposals), 3)
        self.assertEqual(len(changes), 3)
        self.assertEqual(len(fake.calls), 1)

        arxiv_ids, _ = fake.calls[0]
        # generate_review_proposals passes one ID per record; service handles dedupe.
        self.assertEqual(arxiv_ids, ["2401.12345", "2401.12345", "2402.99999"])

    def test_output_order_is_deterministic_and_aligned_to_input(self):
        records = [
            {
                "type": "article",
                "citation_key": "c",
                "fields": {"title": "T3", "eprint": "arxiv:2403.00003"},
            },
            {
                "type": "article",
                "citation_key": "a",
                "fields": {"title": "T1", "eprint": "arxiv:2403.00001"},
            },
            {
                "type": "article",
                "citation_key": "b",
                "fields": {"title": "T2", "eprint": "arxiv:2403.00002"},
            },
        ]

        fake = FakeLookupService()
        proposals, _ = generate_review_proposals(records, lookup_service=fake)

        keys = [p["citation_key"] if p else None for p in proposals]
        self.assertEqual(keys, ["c", "a", "b"])


if __name__ == "__main__":
    unittest.main()
