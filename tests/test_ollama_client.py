import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from legal_email_converter.ollama_client import (
    OllamaClient,
    OllamaModelNotFoundError,
    OllamaUnavailableError,
    query_date_signal_with_ollama,
)


class OllamaClientTests(unittest.TestCase):
    def test_embed_sends_expected_payload(self):
        fake_response = io.BytesIO(json.dumps({"embeddings": [[0.1, 0.2]]}).encode("utf-8"))
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = lambda s, *a: None

        with mock.patch("urllib.request.urlopen", return_value=fake_response) as urlopen_mock:
            client = OllamaClient(base_url="http://localhost:11434/api")
            result = client.embed(model="nomic-embed-text", input_text="hello")

        self.assertIn("embeddings", result)
        req = urlopen_mock.call_args.args[0]
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["model"], "nomic-embed-text")
        self.assertEqual(payload["input"], "hello")

    def test_query_date_signal_parses_json_response(self):
        fake_llm = {
            "response": json.dumps({"date": "2025-06-01", "confidence": 0.8, "source": "content"})
        }
        client = mock.Mock(spec=OllamaClient)
        client.generate.return_value = fake_llm

        out = query_date_signal_with_ollama(
            client=client,
            model="llama3.2:3b",
            kind="PDF",
            relative_path="x.pdf",
            metadata={},
            content="June 1, 2025",
        )
        self.assertEqual(out["value"], "2025-06-01")
        self.assertEqual(out["source"], "query.content")
        self.assertAlmostEqual(float(out["confidence"]), 0.8, places=3)

    def test_query_date_signal_parses_wrapped_json(self):
        client = mock.Mock(spec=OllamaClient)
        client.generate.return_value = {
            "response": 'Here you go: {"date":"2025-02-14","confidence":0.9,"source":"path"}'
        }

        out = query_date_signal_with_ollama(
            client=client,
            model="llama3.2:3b",
            kind="PDF",
            relative_path="x.pdf",
            metadata={},
            content="",
        )
        self.assertEqual(out["value"], "2025-02-14")
        self.assertEqual(out["source"], "query.path")

    def test_query_date_signal_repairs_once(self):
        client = mock.Mock(spec=OllamaClient)
        client.generate.side_effect = [
            {"response": "not json"},
            {"response": '{"date":"2025-01-01","confidence":0.7,"source":"metadata"}'},
        ]

        out = query_date_signal_with_ollama(
            client=client,
            model="llama3.2:3b",
            kind="MSG",
            relative_path="a.msg",
            metadata={"Date": "2025-01-01"},
            content="",
        )
        self.assertEqual(out["value"], "2025-01-01")
        self.assertEqual(out["source"], "query.metadata")
        self.assertEqual(client.generate.call_count, 2)

    def test_ping_and_list_models(self):
        def mk_response():
            resp = io.BytesIO(
                json.dumps({"models": [{"name": "llama3.2:3b"}, {"name": "qwen3-coder:30b"}]}).encode("utf-8")
            )
            resp.__enter__ = lambda s: s
            resp.__exit__ = lambda s, *a: None
            return resp

        with mock.patch("urllib.request.urlopen", side_effect=[mk_response(), mk_response()]):
            client = OllamaClient(base_url="http://localhost:11434/api")
            self.assertTrue(client.ping())
            self.assertEqual(client.list_models(), ["llama3.2:3b", "qwen3-coder:30b"])

    def test_model_not_found_maps_to_specific_error(self):
        err = urllib.error.HTTPError(
            url="http://localhost:11434/api/generate",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"model not found"}'),
        )
        with mock.patch("urllib.request.urlopen", side_effect=err):
            client = OllamaClient(base_url="http://localhost:11434/api")
            with self.assertRaises(OllamaModelNotFoundError):
                client.generate(model="missing:model", prompt="x")

    def test_unavailable_maps_to_unavailable_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            client = OllamaClient(base_url="http://localhost:11434/api")
            with self.assertRaises(OllamaUnavailableError):
                client.ping()


if __name__ == "__main__":
    unittest.main()
