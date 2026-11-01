from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class HandoffConfigTests(unittest.TestCase):
    def test_sample_source_paths_exist_when_running_from_backend(self):
        for sample in (ROOT/".env.example",ROOT/"backend/.env.example"):
            setting=next(l for l in sample.read_text().splitlines() if l.startswith("RAG_SOURCE_PATHS="))
            relative=setting.split("=",1)[1].strip('"')
            self.assertEqual((ROOT/"backend"/relative).resolve(),ROOT/"data/chunks")
            self.assertTrue((ROOT/"backend"/relative).is_dir())

    def test_compose_context_matches_dockerfile_and_separates_host_urls(self):
        compose=(ROOT/"docker-compose.yml").read_text()
        self.assertIn("context: .\n",compose)
        self.assertIn("dockerfile: backend/Dockerfile",compose)
        for line in (ROOT/"backend/Dockerfile").read_text().splitlines():
            if line.startswith("COPY "):
                self.assertTrue((ROOT/line.split()[1]).exists())
        self.assertIn("${DOCKER_LLM_BASE_URL:",compose)
        self.assertIn("${DOCKER_EMBEDDING_BASE_URL:",compose)
        self.assertNotIn("${LLM_BASE_URL:",compose)

    def test_ai_guidance_uses_current_paths_and_test_commands(self):
        for name in ("CLAUDE.md","AGENTS.md",".agents/skills/modsa-backend/SKILL.md"):
            text=(ROOT/name).read_text()
            self.assertNotIn("backend_new/",text)
            self.assertNotIn("backend_old/",text)
            self.assertIn("graph/",text)
        self.assertIn("graph/tests",(ROOT/"AGENTS.md").read_text())


if __name__ == "__main__":
    unittest.main()
