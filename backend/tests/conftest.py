import os
import tempfile

# Keep ML artefacts out of /app/models when running tests locally.
os.environ.setdefault("ML_MODEL_PATH", os.path.join(tempfile.gettempdir(), "smartplan-test-models"))
os.environ.setdefault("DEBUG", "false")
