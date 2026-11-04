"""Answer-provider binding checks; no real credentials, clients or API calls."""
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, sentinel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with patch("dotenv.load_dotenv", return_value=False):
    llm = importlib.import_module("core.llm")
    from config import Settings


class AnswerLLMProviderTests(unittest.TestCase):
    def settings(self):
        return Settings(
            _env_file=None,
            LLM_MODEL="gemma4:31b-cloud",
            LLM_BASE_URL="http://localhost:11434/v1",
            LLM_API_KEY="fake-test-key",
            LLM_TIMEOUT=12,
            LLM_MAX_RETRIES=0,
        )

    def test_answer_client_uses_llm_settings_not_mimo_extraction_credentials(self):
        settings = self.settings()
        with patch.dict("os.environ", {"MIMO_API_KEY": "not-for-answer"}), \
             patch.object(llm, "_llm", None), \
             patch.object(llm, "ChatOpenAI", return_value=sentinel.client) as client:
            self.assertIs(llm.build_llm(settings), sentinel.client)
        client.assert_called_once_with(
            model="gemma4:31b-cloud",
            api_key="fake-test-key",
            base_url="http://localhost:11434/v1",
            temperature=0,
            timeout=12,
            max_retries=0,
        )

    def test_answer_client_is_reused_within_process(self):
        settings = self.settings()
        with patch.object(llm, "_llm", None), \
             patch.object(llm, "ChatOpenAI", return_value=sentinel.client) as client:
            self.assertIs(llm.build_llm(settings), llm.build_llm(settings))
        client.assert_called_once()

    def test_different_settings_never_reuse_the_previous_model_or_credentials(self):
        first = self.settings()
        for change in ({"llm_model":"qwen-test"}, {"llm_base_url":"http://localhost:9999/v1"},
                       {"llm_api_key":"different-fake-key"}, {"llm_timeout":99}, {"llm_max_retries":2}):
            with self.subTest(fields=list(change)), patch.object(llm,"_llm",None), \
                 patch.object(llm,"ChatOpenAI",side_effect=[sentinel.first,sentinel.second]) as client:
                self.assertIs(llm.build_llm(first),sentinel.first)
                self.assertIs(llm.build_llm(first.model_copy(update=change)),sentinel.second)
                self.assertEqual(client.call_count,2)


if __name__ == "__main__":
    unittest.main()
