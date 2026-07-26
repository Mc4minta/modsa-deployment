import unittest

from pydantic import ValidationError

from schemas.chat import AskRequest


class AskRequestTests(unittest.TestCase):
    def test_question_is_trimmed(self) -> None:
        request = AskRequest(question="  How do I register?  ")
        self.assertEqual(request.question, "How do I register?")

    def test_blank_question_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AskRequest(question="   ")

    def test_question_over_limit_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AskRequest(question="x" * 1501)


if __name__ == "__main__":
    unittest.main()
