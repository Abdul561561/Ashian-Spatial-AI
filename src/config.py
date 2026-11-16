import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "particle-ai/particle-1:free")
OPENROUTER_FALLBACK_MODEL = os.getenv("OPENROUTER_FALLBACK_MODEL", "cohere/north-mini-code:free")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Paths
DATASET_RAW_DIR = BASE_DIR / os.getenv("DATASET_RAW_DIR", "data/raw")
DATASET_X_DIR = DATASET_RAW_DIR / "X"
DATASET_Y_DIR = DATASET_RAW_DIR / "Y"
PROCESSED_DATA_DIR = BASE_DIR / os.getenv("PROCESSED_DATA_DIR", "data/processed")
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "outputs")

# Database Configuration
DEFAULT_DB_PATH = BASE_DIR / "data" / "spatial_ai.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# Ensure runtime directories exist
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Dataset Class Definition based on CVC-FP Analysis
# Exact color profiles (RGB values and color distance thresholds)
CLASS_PALETTE = {
    "background": {
        "rgb": (0, 0, 0),
        "hex": "#000000",
        "description": "Exterior background / canvas",
        "color_tolerance": 25,
    },
    "room": {
        "rgb": (0, 142, 142),
        "hex": "#008E8E",
        "description": "Primary room / enclosed interior space (Living, Bedroom, Hall)",
        "color_tolerance": 30,
    },
    "door": {
        "rgb": (255, 142, 70),
        "hex": "#FF8E46",
        "description": "Door / opening connecting spaces",
        "color_tolerance": 35,
    },
    "window": {
        "rgb": (246, 189, 15),
        "hex": "#F6BD0F",
        "description": "Window / facade daylight opening",
        "color_tolerance": 35,
    },
    "wall": {
        "rgb": (175, 216, 248),
        "hex": "#AFD8F8",
        "description": "Wall / structural partition",
        "color_tolerance": 35,
    },
    "service_room": {
        "rgb": (214, 70, 70),
        "hex": "#D64646",
        "description": "Service space / Bathroom / Restroom / Storage",
        "color_tolerance": 30,
    },
    "balcony": {
        "rgb": (139, 186, 0),
        "hex": "#8BBA00",
        "description": "Balcony / Outdoor terrace / Exterior access",
        "color_tolerance": 30,
    },
}
