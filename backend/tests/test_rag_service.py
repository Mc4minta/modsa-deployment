import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services import rag_service


class RagServiceTests(unittest.TestCase):
    def test_empty_llm_content_uses_safe_fallback_and_logs_finish_reason(self):
        document = SimpleNamespace(
            metadata={"source": "handbook.pdf"},
            page_content="Verified context",
        )
        response = SimpleNamespace(
            content="",
            response_metadata={"finish_reason": "length"},
        )
        settings = SimpleNamespace(retrieval_k=4)

        with (
            patch.object(rag_service, "retrieve_documents", return_value=[document]),
            patch.object(rag_service, "build_llm") as build_llm,
            self.assertLogs(rag_service.logger, level=logging.WARNING) as logs,
        ):
            build_llm.return_value.invoke.return_value = response
            result = rag_service.answer_question(settings, "What is this?")

        self.assertEqual(result["answer"], rag_service.NO_VERIFIED_INFO_EN)
        self.assertEqual(result["sources"], [{"source": "handbook.pdf"}])
        self.assertIn("finish_reason=length", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
