# Cloud development setup

Use the existing `/workspace/TerraMind` checkout. Cloud tasks are already isolated;
do not create a Git worktree unless explicitly requested.

Run `bash scripts/setup-cloud.sh` from the repository root. The script installs
the locked frontend dependencies, the backend virtual environment, and a separate
ML virtual environment. Its npm cache is writable under `/workspace`.

For the default sandbox workflow:

```sh
cd /workspace/TerraMind/frontend
npm run dev -- --hostname 0.0.0.0
```

Check port 3000 with a local HTTP request and open it with a browser. The dashboard
must appear without sign-in or an authentication request. Stop the server before
reinstalling frontend dependencies. Live processes need restarting in a new task.

Validation:

```sh
cd /workspace/TerraMind/frontend
npm run check
cd /workspace/TerraMind/backend
.venv/bin/python -m pytest -q
cd /workspace/TerraMind
python3 -m unittest discover -s checks -v
MPLCONFIGDIR=/workspace/.cache/matplotlib /workspace/.venvs/terramind-ml/bin/python -m unittest discover -s tests_ml -v
```

Browser tests use the installed Chromium or `CHROMIUM_PATH` before falling back
to a downloaded Playwright browser. The sandbox needs no backend services or
provider secrets. Real private workflows require the services in `DEPLOYMENT.md`.

To train without replacing committed artifacts:

```sh
cd /workspace/TerraMind
TERRAMIND_OUTPUT_DIR=/workspace/terramind-validation/ml MPLCONFIGDIR=/workspace/.cache/matplotlib /workspace/.venvs/terramind-ml/bin/python ml_models/yield_predictor.py
```

These instructions are also the fallback if the cloud configuration draft service
cannot persist the installation/startup fields. Repository instructions alone do
not publish an environment snapshot.
