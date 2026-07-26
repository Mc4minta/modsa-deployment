import unittest

from prompts.rag_prompt import SYSTEM_PROMPT


class RagPromptTests(unittest.TestCase):
    def test_prompt_keeps_context_placeholder(self) -> None:
        self.assertIn("{context}", SYSTEM_PROMPT)

    def test_prompt_requires_grounding_and_citations(self) -> None:
        self.assertIn("Use only facts in the retrieved context", SYSTEM_PROMPT)
        self.assertIn("Cite factual claims", SYSTEM_PROMPT)
        self.assertIn("Markdown table", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
