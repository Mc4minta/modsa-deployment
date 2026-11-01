"""Provider selection is offline and does not import unused Hugging Face code."""
import builtins
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch, sentinel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with patch("dotenv.load_dotenv", return_value=False):
    embeddings = importlib.import_module("core.embeddings")


class EmbeddingProviderTests(unittest.TestCase):
    def settings(self, provider):
        return SimpleNamespace(
            embedding_provider=provider,
            embedding_model="test-model",
            resolved_embedding_base_url="http://localhost:11434",
            embedding_base_url="https://example.invalid/v1",
            resolved_embedding_api_key="unit-test-key",
            embedding_timeout=12,
            embedding_max_retries=1,
        )

    def test_ollama_does_not_import_huggingface(self):
        original_import = builtins.__import__

        def without_huggingface(name, *args, **kwargs):
            if name.startswith("langchain_huggingface"):
                raise AssertionError("Ollama must not import Hugging Face")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=without_huggingface), \
             patch.object(embeddings, "OllamaEmbeddings", return_value=sentinel.client) as client:
            self.assertIs(embeddings.build_embeddings(self.settings("ollama")), sentinel.client)
        client.assert_called_once_with(model="test-model", base_url="http://localhost:11434")

    def test_openai_does_not_require_huggingface_and_preserves_client_settings(self):
        with patch.dict(sys.modules, {"langchain_huggingface": None}), \
             patch.object(embeddings, "OpenAIEmbeddings", return_value=sentinel.client) as client:
            self.assertIs(embeddings.build_embeddings(self.settings("openai")), sentinel.client)
        client.assert_called_once_with(model="test-model", api_key="unit-test-key",
            base_url="https://example.invalid/v1", timeout=12, max_retries=1)

    def test_huggingface_missing_dependency_has_clear_error(self):
        with patch.dict(sys.modules, {"langchain_huggingface": None}), \
             self.assertRaisesRegex(RuntimeError, "EMBEDDING_PROVIDER=huggingface requires langchain-huggingface") as error:
            embeddings.build_embeddings(self.settings("huggingface"))
        self.assertNotIn("unit-test-key", str(error.exception))

    def test_huggingface_imports_only_when_selected(self):
        module = ModuleType("langchain_huggingface")
        client = Mock(return_value=sentinel.client)
        module.HuggingFaceEndpointEmbeddings = client
        with patch.dict(sys.modules, {"langchain_huggingface": module}):
            self.assertIs(embeddings.build_embeddings(self.settings("huggingface")), sentinel.client)
        client.assert_called_once_with(model="test-model", huggingfacehub_api_token="unit-test-key")

    def test_huggingface_transitive_import_error_is_not_masked(self):
        original_import = builtins.__import__
        missing = ModuleNotFoundError("Missing internal dependency", name="huggingface_hub")

        def unavailable_transitive_dependency(name, *args, **kwargs):
            if name == "langchain_huggingface":
                raise missing
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=unavailable_transitive_dependency), \
             self.assertRaises(ModuleNotFoundError) as error:
            embeddings.build_embeddings(self.settings("huggingface"))
        self.assertIs(error.exception, missing)


if __name__ == "__main__":
    unittest.main()
