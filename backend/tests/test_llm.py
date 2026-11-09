import unittest

from config import Settings
import core.llm as llm_module


class LlmFactoryTests(unittest.TestCase):
    def setUp(self):
        llm_module._llm = None

    def tearDown(self):
        llm_module._llm = None

    def test_optional_settings_are_omitted_by_default(self):
        settings = Settings(
            LLM_BASE_URL="https://gateway.example/v1",
            LLM_API_KEY="test-key",
            LLM_MODEL="test-model",
        )

        model = llm_module.build_llm(settings)

        self.assertIsNone(model.extra_body)
        self.assertIsNone(model.model_dump().get("max_tokens"))

    def test_optional_settings_are_forwarded(self):
        settings = Settings(
            LLM_BASE_URL="https://gateway.example/v1",
            LLM_API_KEY="test-key",
            LLM_ENABLE_THINKING=False,
            LLM_MAX_TOKENS=800,
        )

        model = llm_module.build_llm(settings)

        self.assertEqual(
            model.extra_body,
            {"chat_template_kwargs": {"enable_thinking": False}},
        )
        self.assertEqual(model.model_dump()["max_tokens"], 800)

    def test_max_tokens_must_be_positive(self):
        with self.assertRaises(ValueError):
            Settings(LLM_MAX_TOKENS=0)


if __name__ == "__main__":
    unittest.main()
