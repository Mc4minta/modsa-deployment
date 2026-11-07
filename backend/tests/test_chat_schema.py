import unittest

try:
    from pydantic import ValidationError
    from schemas.chat import AskRequest
    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False


class AskRequestTests(unittest.TestCase):
    def setUp(self):
        if not _DEPS_AVAILABLE:
            self.skipTest("Pydantic is not installed in the environment")

    def test_trims_question(self):
        self.assertEqual(AskRequest(question="  hello  ").question, "hello")

    def test_rejects_blank_question(self):
        with self.assertRaises(ValidationError):
            AskRequest(question=" \t\n ")

    def test_rejects_question_over_limit(self):
        with self.assertRaises(ValidationError):
            AskRequest(question="a" * 1501)

    def test_rejects_sensitive_values(self):
        for question in (
            "api_key=sk-test-value-that-is-long-enough",
            "เลขบัตรประชาชน 1101700203456",
            "1101700203456",
        ):
            with self.subTest(question=question):
                with self.assertRaises(ValidationError):
                    AskRequest(question=question)

    def test_rejects_attachment_fields(self):
        with self.assertRaises(ValidationError):
            AskRequest(question="hello", attachments=[])


if __name__ == "__main__":
    unittest.main()
