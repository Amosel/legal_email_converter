import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from legal_email_converter.ollama_client import OllamaClient, query_date_signal_with_ollama


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


if __name__ == "__main__":
    unittest.main()
