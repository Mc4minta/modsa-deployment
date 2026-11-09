import logging
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app


class ChatApiTests(unittest.TestCase):
    def test_unexpected_error_is_sanitized_and_logged(self):
        client = TestClient(app)

        with (
            patch(
                "api.chat.answer_question",
                side_effect=RuntimeError("gateway secret details"),
            ),
            self.assertLogs("api.chat", level=logging.INFO) as logs,
        ):
            response = client.post(
                "/chat/ask",
                json={"question": "test question"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Internal server error"})
        self.assertNotIn("gateway secret details", response.text)
        self.assertTrue(
            any(
                "outcome=error" in message
                and "exception=RuntimeError" in message
                for message in logs.output
            )
        )


if __name__ == "__main__":
    unittest.main()
