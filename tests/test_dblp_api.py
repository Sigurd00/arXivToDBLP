import unittest
from unittest.mock import Mock, patch

import requests

import dblp_api


class DblpApiTests(unittest.TestCase):
    @patch('dblp_api.requests.get')
    @patch('dblp_api.time.sleep', return_value=None)
    def test_retry_behavior_then_success(self, mock_sleep, mock_get):
        first = requests.RequestException('temporary')
        second = Mock(status_code=500)
        third = Mock(status_code=200)
        third.json.return_value = {'result': {'hits': {'@total': '0', 'hit': []}}}
        mock_get.side_effect = [first, second, third]

        payload = dblp_api.try_fetch_from_dblp('1234.5678', max_retries=3)

        self.assertEqual(payload, {'result': {'hits': {'@total': '0', 'hit': []}}})
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    @patch('dblp_api.try_fetch_from_dblp')
    def test_zero_hits_returns_none(self, mock_fetch):
        mock_fetch.return_value = {'result': {'hits': {'@total': '0', 'hit': []}}}
        self.assertIsNone(dblp_api.find_dblp_citation('1234.5678', 'k'))

    @patch('dblp_api.try_fetch_from_dblp')
    def test_malformed_payload_raises_for_unexpected_hit_shape(self, mock_fetch):
        mock_fetch.return_value = {'result': {'hits': {'@total': '1', 'hit': {'info': {}}}}}
        with self.assertRaises((TypeError, KeyError, AttributeError, IndexError)):
            dblp_api.find_dblp_citation('1234.5678', 'k')


if __name__ == '__main__':
    unittest.main()
