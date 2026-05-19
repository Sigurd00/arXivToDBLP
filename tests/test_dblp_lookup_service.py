import unittest

from dblp_api import DblpLookupService


class StubService(DblpLookupService):
    def __init__(self):
        super().__init__(max_concurrency=2, total_timeout_budget=2, cache_ttl_seconds=60)
        self.fetch_count = {}

    def _fetch_one(self, arxiv_id, original_key):
        self.fetch_count[arxiv_id] = self.fetch_count.get(arxiv_id, 0) + 1
        return {
            "type": "article",
            "citation_key": original_key,
            "fields": {"title": f"Paper {arxiv_id}", "author": "X"},
        }


class DblpLookupServiceTests(unittest.TestCase):
    def test_dedupes_repeated_ids_within_batch(self):
        svc = StubService()
        out = svc.lookup_many(
            ["2401.00001", "2401.00001", "2402.00002"],
            ["k1", "k2", "k3"],
        )
        self.assertEqual(svc.fetch_count.get("2401.00001"), 1)
        self.assertEqual(svc.fetch_count.get("2402.00002"), 1)
        self.assertEqual([r["citation_key"] for r in out], ["k1", "k2", "k3"])

    def test_cache_avoids_followup_network_calls(self):
        svc = StubService()
        svc.lookup_many(["2401.00001"], ["k1"])
        svc.lookup_many(["2401.00001"], ["k1b"])
        self.assertEqual(svc.fetch_count.get("2401.00001"), 1)

    def test_none_results_are_cached(self):
        class NoneService(StubService):
            def _fetch_one(self, arxiv_id, original_key):
                self.fetch_count[arxiv_id] = self.fetch_count.get(arxiv_id, 0) + 1
                return None

        svc = NoneService()
        svc.lookup_many(["2409.00009"], ["k1"])
        svc.lookup_many(["2409.00009"], ["k2"])
        self.assertEqual(svc.fetch_count.get("2409.00009"), 1)


if __name__ == "__main__":
    unittest.main()
