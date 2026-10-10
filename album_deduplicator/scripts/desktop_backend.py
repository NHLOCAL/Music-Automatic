"""Entry point for the bundled desktop server (no external Python required)."""
import argparse
import json
import multiprocessing
from pathlib import Path
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def model_probe():
    import hashlib
    import numpy as np
    from music_dup_lib.external.ml_similarity_model import MLSimilarityModel

    model = MLSimilarityModel()
    if not model.model_loaded:
        raise RuntimeError("Bundled ML model could not be loaded")
    width = model.model.n_features_in_
    matrix = np.random.default_rng(42).uniform(0, 100, (32, width))
    return {
        "model_sha256": hashlib.sha256(model.resolved_model_path.read_bytes()).hexdigest(),
        "predictions": np.asarray(model.model.predict(matrix)).tolist(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    # A missing model is a packaging error, never a silent accuracy downgrade.
    probe = model_probe()
    from api.app import app
    if args.self_test:
        print(json.dumps(probe))
        return
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_config=None)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
