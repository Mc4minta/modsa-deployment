from pathlib import Path

ROOT = Path("./")

directories = [
    # Frontend
    "frontend/src/components",
    "frontend/src/pages",
    "frontend/src/hooks",
    "frontend/src/services",
    "frontend/src/router",
    "frontend/src/assets",
    "frontend/public",

    # Backend
    "backend/app/api",
    "backend/app/core",
    "backend/app/models",
    "backend/app/schemas",
    "backend/app/services",
    "backend/app/database",
    "backend/app/utils",
    "backend/data/chroma",
    "backend/data/knowledge",

    # Development scripts
    "scripts",

    # Dataset management
    "datasets/raw",
    "datasets/processed",
    "datasets/evaluation",
    "datasets/merged",

    # Documentation
    "docs",
]

files = [
    # Frontend
    "frontend/.env.example",

    # Backend
    "backend/requirements.txt",
    "backend/Dockerfile",
    "backend/.env.example",
    "backend/render.yaml",

    # Root
    "README.md",
    ".gitignore",
    "docker-compose.yml",

    # Documentation
    "docs/Architecture.md",
    "docs/Deployment.md",
    "docs/API.md",
    "docs/RAG.md",
    "docs/Evaluation.md",

    # Scripts placeholders
    "scripts/build_embeddings.py",
    "scripts/chunk_documents.py",
    "scripts/ingest_documents.py",
    "scripts/evaluate.py",
    "scripts/export_dataset.py",
]


def create_structure():
    print(f"Creating structure in: {ROOT.resolve()}")

    # Create directories
    for directory in directories:
        path = ROOT / directory
        path.mkdir(parents=True, exist_ok=True)
        print(f"[DIR]  {path}")

    # Create empty files
    for file in files:
        path = ROOT / file
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            path.touch()
            print(f"[FILE] {path}")
        else:
            print(f"[SKIP] {path} already exists")

    print("\nDirectory structure created successfully.")
    print("No existing files were moved or modified.")


if __name__ == "__main__":
    create_structure()