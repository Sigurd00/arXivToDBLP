import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import app as app_module


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        app_module.app.config['TESTING'] = True
        app_module.STATE_DIR = self.tmpdir.name
        os.makedirs(app_module.STATE_DIR, exist_ok=True)
        self.client = app_module.app.test_client()

    def _post_bib(self, bib_bytes: bytes):
        return self.client.post(
            '/review',
            data={'bibfile': (io.BytesIO(bib_bytes), 'in.bib')},
            content_type='multipart/form-data',
        )

    def test_upload_validation(self):
        resp = self.client.post('/review', data={}, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/', resp.location)

    @patch('app._process_review_job')
    def test_review_starts_async_job_and_status_endpoint(self, mock_process):
        bib = b"""
@article{k1,
 title={Old},
 url={https://arxiv.org/abs/1234.5678}
}
"""
        resp = self._post_bib(bib)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/review/', resp.location)

        token = resp.location.rsplit('/', 1)[-1]
        status_resp = self.client.get(f'/review_status/{token}')
        self.assertEqual(status_resp.status_code, 200)
        payload = status_resp.get_json()
        self.assertEqual(payload['status'], 'queued')
        mock_process.assert_called_once()

    def test_finalize_with_accepted_indices(self):
        token = 'tok'
        state = {
            'records': [{'type': 'misc', 'citation_key': 'k1', 'fields': {'title': 'Old'}}],
            'proposals': [{'type': 'article', 'citation_key': 'k1', 'fields': {'title': 'New'}}],
            'changes': [{'modified': {'title': {'from': 'Old', 'to': 'New'}}, 'added': {}, 'removed': {}, 'type_changed': {'from': 'misc', 'to': 'article'}}],
        }
        with open(app_module._state_path(token), 'w', encoding='utf-8') as f:
            json.dump(state, f)

        resp = self.client.post('/finalize', data={'token': token, 'accept': '0'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('converted.bib', resp.headers.get('Content-Disposition', ''))
        self.assertIn(b'@article{k1,', resp.data)

    def test_missing_and_expired_token_flows(self):
        missing = self.client.post('/finalize', data={})
        self.assertEqual(missing.status_code, 302)

        expired = self.client.post('/finalize', data={'token': 'does-not-exist'})
        self.assertEqual(expired.status_code, 302)


if __name__ == '__main__':
    unittest.main()
