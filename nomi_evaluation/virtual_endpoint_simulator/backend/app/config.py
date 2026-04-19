import logging
import os
import sys
from pathlib import Path

import yaml

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("config")

# Calculate roots dynamically (works in standalone repo or monorepo)
current_file = Path(__file__).resolve()

# Simulator Root (where config.yaml resides): nomi_evaluation/virtual_endpoint_simulator
simulator_root = current_file.parents[2]

# Optional workspace root candidate when running inside a larger monorepo
project_root = simulator_root.parent.parent if len(simulator_root.parents) >= 2 else None

# 1. Try to load config.yaml
config_yaml_path = simulator_root / "config.yaml"
yaml_config = {}
yaml_datasets = {}
yaml_llm = {}

if config_yaml_path.exists():
    try:
        with open(config_yaml_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f) or {}
            yaml_datasets = yaml_config.get("datasets", {}) or {}
            yaml_llm = yaml_config.get("llm", {}) or {}

            # Backward compatibility for old config format:
            # dataset.path -> datasets.ntu_skeleton_dir
            legacy_dataset = yaml_config.get("dataset", {}) or {}
            if "ntu_skeleton_dir" not in yaml_datasets and "path" in legacy_dataset:
                yaml_datasets["ntu_skeleton_dir"] = legacy_dataset["path"]

            if yaml_datasets:
                logger.info(f"Loaded datasets config from config.yaml: {yaml_datasets}")
            if yaml_llm:
                logger.info("Loaded llm config from config.yaml")
    except Exception as e:
        logger.error(f"Failed to load config.yaml: {e}")


def _yaml_dataset_path(key: str):
    """Resolve dataset path from config.yaml (absolute or relative to simulator root)."""
    value = yaml_datasets.get(key)
    if not value:
        return None
    p = Path(str(value))
    if not p.is_absolute():
        p = (simulator_root / p).resolve()
    return str(p)


yaml_ntu_path = _yaml_dataset_path("ntu_skeleton_dir")
yaml_orange4home_path = _yaml_dataset_path("orange4home_dir")
yaml_dalton_path = _yaml_dataset_path("dalton_dir")

# Try to find the skeleton directory
env_ntu_path = os.getenv("NTU_SKELETON_DIR")
workspace_ntu_path = str(project_root / "3d_skeleton" / "skeleton") if project_root else None
local_ntu_path = str(simulator_root / "datasets" / "ntu_skeletons")

possible_paths = [
    # 0. YAML Config (Highest Priority)
    yaml_ntu_path,
    # 1. Environment variable
    env_ntu_path,
    # 2. Standard location in workspace
    workspace_ntu_path,
    # 3. Local standalone default directory
    local_ntu_path,
]

final_path = None
for p in possible_paths:
    if p and Path(p).exists():
        final_path = Path(p)
        break

if final_path:
    DEFAULT_DATASET_DIR = final_path.resolve()
    logger.info(f"Found dataset directory at: {DEFAULT_DATASET_DIR}")
else:
    # Keep a deterministic fallback without machine-specific hardcoded paths
    DEFAULT_DATASET_DIR = Path(env_ntu_path or local_ntu_path)
    logger.warning(f"Could not find dataset in standard locations. Using fallback: {DEFAULT_DATASET_DIR}")

# Orange4Home Config
ORANGE4HOME_DIR = Path(
    yaml_orange4home_path
    or os.getenv(
        "ORANGE4HOME_DIR",
        str(simulator_root / "datasets" / "orange4home")
    )
)
logger.info(f"Using Orange4Home Dir: {ORANGE4HOME_DIR}")

# DALTON Config
DALTON_DIR = Path(
    yaml_dalton_path
    or os.getenv(
        "DALTON_DIR",
        str(simulator_root / "datasets" / "dalton")
    )
)
logger.info(f"Using DALTON Dir: {DALTON_DIR}")

# LLM Judge Config (read from YAML only)
GEMINI_API_KEY = str(yaml_llm.get("api_key", "")).strip()
GEMINI_MODEL_NAME = str(yaml_llm.get("model_name", "gemini-2.0-flash")).strip()
GEMINI_JUDGE_MODEL = str(yaml_llm.get("judge_model", GEMINI_MODEL_NAME)).strip()

if GEMINI_API_KEY:
    logger.info(f"LLM config loaded (model={GEMINI_MODEL_NAME}, judge_model={GEMINI_JUDGE_MODEL})")
    if config_yaml_path.exists():
        logger.warning(
            "config.yaml contains llm.api_key. Keep this file local and do not commit it to Git."
        )
else:
    logger.warning("LLM config missing: llm.api_key is empty in config.yaml")

APP_NAME = "Virtual Endpoint Simulator"
APP_VERSION = "0.2.0"
