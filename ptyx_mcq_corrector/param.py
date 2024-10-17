from pathlib import Path

import platformdirs

RESSOURCES_PATH = Path(__file__).parent.parent / "ressources"
ICON_PATH = RESSOURCES_PATH / "mcq-corrector.svg"
WINDOW_TITLE = "MCQ Corrector"
DEBUG = True
CONFIG_PATH = Path(platformdirs.user_config_path("mcq-corrector") / "config.toml")
MAX_RECENT_FILES = 12
