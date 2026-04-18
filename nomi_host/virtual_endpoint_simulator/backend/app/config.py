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

# Calculate project root dynamically by searching upwards
current_file = Path(__file__).resolve()
project_root = None

# Simulator Root (where config.yaml resides) should be 'nomi_host/virtual_endpoint_simulator'
# We are in 'nomi_host/virtual_endpoint_simulator/backend/app/config.py'
# So simulator root is ../..
simulator_root = current_file.parents[2]

# Search for the marker "3d_skeleton" directory in parent directories for WORKSPACE root
for parent in current_file.parents:
    if (parent / "3d_skeleton").exists():
        project_root = parent
        break
    if (parent / "sscma-example-we2").exists():
        pass

if not project_root:
    try:
        project_root = current_file.parents[4]
    except IndexError:
        project_root = current_file.parent

# 1. Try to load config.yaml
config_yaml_path = simulator_root / "config.yaml"
yaml_dataset_path = None

if config_yaml_path.exists():
    try:
        with open(config_yaml_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config and "dataset" in yaml_config and "path" in yaml_config["dataset"]:
                yaml_dataset_path = yaml_config["dataset"]["path"]
                logger.info(f"Loaded dataset path from config.yaml: {yaml_dataset_path}")
    except Exception as e:
        logger.error(f"Failed to load config.yaml: {e}")

# Try to find the skeleton directory
possible_paths = [
    # 0. YAML Config (Highest Priority)
    yaml_dataset_path,
    # 1. Environment variable
    os.getenv("NTU_SKELETON_DIR"),
    # 2. Standard location in workspace
    str(project_root / "3d_skeleton" / "skeleton") if project_root else None,
    # 3. Fallback: look relative to current file (for testing)
    str(current_file.parent / "../../../../../3d_skeleton/skeleton"),
    # 4. Hardcoded known path
    "/Users/freddy/Documents/251006_WiseEye2/sscma-example-we2/3d_skeleton/skeleton"
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
    # Fallback to the original hardcoded path if nothing found (legacy behavior)
    DEFAULT_DATASET_DIR = Path(
        os.getenv(
            "NTU_SKELETON_DIR",
            "/Users/freddy/Documents/260213_NOMI_evaluation/NTU_RGB/nturgb+d_skeletons",
        )
    )
    logger.warning(f"Could not find dataset in standard locations. Using fallback: {DEFAULT_DATASET_DIR}")

# Orange4Home Config
ORANGE4HOME_DIR = Path(
    os.getenv(
        "ORANGE4HOME_DIR",
        "/Users/freddy/Documents/260213_NOMI_evaluation/Orange4Home/orange4home"
    )
)
logger.info(f"Using Orange4Home Dir: {ORANGE4HOME_DIR}")

# DALTON Config
DALTON_DIR = Path(
    os.getenv(
        "DALTON_DIR",
        "/Users/freddy/Documents/260213_NOMI_evaluation/DALTON/dalton-dataset-files"
    )
)
logger.info(f"Using DALTON Dir: {DALTON_DIR}")

APP_NAME = "Virtual Endpoint Simulator"
APP_VERSION = "0.2.0"
