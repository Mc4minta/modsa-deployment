import unittest
from unittest.mock import patch

try:
    from fastapi import HTTPException
    from api.chat import ask
    from schemas.chat import AskRequest
    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False


class ChatApiTests(unittest.TestCase):
    def test_ask_sanitizes_500_error_detail(self):
        if not _DEPS_AVAILABLE:
            self.skipTest("FastAPI or backend dependencies not available in current environment")

        with patch("api.chat.answer_question", side_effect=RuntimeError("internal secret database failure")):
            with patch("api.chat.get_settings"):
                request = AskRequest(question="What is the tuition fee?")
                with self.assertRaises(HTTPException) as ctx:
                    ask(request)
                self.assertEqual(ctx.exception.status_code, 500)
                self.assertEqual(ctx.exception.detail, "Internal server error")
                self.assertNotIn("internal secret database failure", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
