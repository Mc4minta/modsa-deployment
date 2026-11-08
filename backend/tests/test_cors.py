import unittest

from fastapi.testclient import TestClient

from main import app


class CorsTests(unittest.TestCase):
    def test_preflight_allows_ngrok_header_for_configured_origin(self):
        client = TestClient(app)
        response = client.options(
            "/chat/ask",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": (
                    "content-type,ngrok-skip-browser-warning"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )
        self.assertIn(
            "ngrok-skip-browser-warning",
            response.headers["access-control-allow-headers"],
        )
        self.assertEqual(response.headers["access-control-max-age"], "7200")

    def test_preflight_rejects_non_listed_origin(self):
        client = TestClient(app)
        response = client.options(
            "/chat/ask",
            headers={
                "Origin": "https://not-configured.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertNotEqual(
            response.headers.get("access-control-allow-origin"),
            "https://not-configured.example",
        )


if __name__ == "__main__":
    unittest.main()
