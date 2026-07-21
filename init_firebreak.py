# This script generates the entire project skeleton.
import os, shutil, stat

BASE = os.getcwd()  # current directory
SKEL = {
    "README.md": """# Firebreak‑X\n**Universal Offensive Orchestration Framework**\n\n## Status\n🚧 Under active development.\n\n## Quick Start\n```bash\ndocker-compose up -d\n```\n""",
    ".gitignore": """venv/\n__pycache__/\n*.pyc\n*.log\n.env\n.DS_Store\n*.pem\n*.key\noutput/\nresults/\n""",
    "requirements.txt": """celery==5.3.4\nredis==5.0.1\nflask==3.0.0\nrequests==2.31.0\npyyaml==6.0.1\npytest==7.4.3\n""",
    "docker/docker-compose.yml": """version: '3.8'\nservices:\n  redis:\n    image: redis:alpine\n    ports:\n      - "6379:6379"\n  orchestrator:\n    build:\n      context: ..\n      dockerfile: docker/orchestrator.Dockerfile\n    depends_on:\n      - redis\n    ports:\n      - "5000:5000"\n""",
    "playbooks/default.yaml": """name: "Default Attack"\ntarget: "https://example.com"\nphases:\n  - name: "recon"\n    tools:\n      - tool: nmap\n        args: ["-sV", "-p-"]\n""",
    ".github/workflows/test.yml": """name: Tests\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v3\n      - uses: actions/setup-python@v4\n        with:\n          python-version: '3.12'\n      - run: pip install -r requirements.txt\n      - run: pytest tests/\n""",
    # Add a minimal setup.py and __init__.py files
    "setup.py": """from setuptools import setup, find_packages\nsetup(name="firebreak", version="0.1.0", packages=find_packages(where="src"), package_dir={"": "src"})\n""",
    "src/__init__.py": "",
    "src/orchestrator/__init__.py": "",
    "src/tools/__init__.py": "",
    "src/ai/__init__.py": "",
    "src/web/__init__.py": "",
    "tests/__init__.py": "",
    "docker/orchestrator.Dockerfile": "FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install -r requirements.txt\nCOPY src/ /app/src/\nCMD [\"celery\", \"-A\", \"orchestrator.tasks\", \"worker\"]\n",
}

for path, content in SKEL.items():
    full = os.path.join(BASE, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if not os.path.exists(full):
        with open(full, "w") as f:
            f.write(content)
        print(f"Created: {path}")
    else:
        print(f"Skipped (exists): {path}")

print("\n✅ Project skeleton created. Now run:")
print("  git add .")
print("  git commit -m 'Initial skeleton'")
print("  git push origin main")
