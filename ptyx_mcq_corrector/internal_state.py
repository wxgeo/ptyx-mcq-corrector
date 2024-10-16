import tomllib
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Iterator, Any

import platformdirs
from tomli_w import dumps

CONFIG_PATH = Path(platformdirs.user_config_path("mcq-editor") / "config.toml")
MAX_RECENT_FILES = 12


class CurrentAction(Enum):
    NONE = auto()
    IN_PROGRESS = auto()
    MISSING_NAME = auto()
    DUPLICATE_PAGES = auto()
    DUPLICATE_NAMES = auto()
    ANSWERS_REVIEW = auto()
    MISSING_PAGES = auto()
    RESULTS = auto()


# @dataclass
# class InternalState:
#     config_file: Path|None = None
#     current_action: CurrentAction|None = None
#     current_picture: Path|None = None
#     checkable_areas: list[tuple] = field(default_factory=list)


@dataclass(kw_only=True)
class Settings:
    """The application current state.

    This includes:
    - tabs opened on
    - recent files
    """

    _recent_dirs: list[Path] = field(default_factory=list)
    _current_dir: Path | None = None
    current_action: CurrentAction | None = None
    current_picture: Path | None = None
    checkable_areas: list[tuple] = field(default_factory=list)

    @property
    def default_dir(self) -> Path:
        """Default directory proposed when opening a file.

        This is the folder containing the current file, if saved on disk.
        Else, it is last used directory.
        """
        return self._current_dir if self._current_dir is not None else Path.cwd()

    @property
    def current_dir(self) -> Path | None:
        return self._current_dir

    @staticmethod
    def is_ptyx_directory(path: Path) -> bool:
        path = path.resolve()
        return path.is_dir() and sum(1 for _ in path.parent.glob("*.ptyx.mcq.config.json")) == 1

    def open_dir(self, directory: Path) -> bool:
        """Open directory.

        Before opening, verification occurs:
        - `directory` must effectively be a directory.
        - it must contain a unique mcq configuration file (i.e. a `.ptyx.mcq.config.json` file.)

        Return a boolean, indicating if the current directory was effectively changed."""
        # Attention, paths must be resolved to don't miss duplicates (symlinks...)!
        # Do nothing if it's the current directory.
        if self.is_ptyx_directory(directory) and directory.resolve() != self._current_dir.resolve():
            self.close_dir()
            self._current_dir = directory
            return True
        return False

    def close_dir(self) -> None:
        if self._current_dir is not None:
            self._remember_dir(self._current_dir)

    def _remember_dir(self, new_path: Path) -> None:
        # The same file must not appear twice in the list.
        self._recent_dirs = [new_path] + [
            path for path in self._recent_dirs if path.resolve() != new_path.resolve() and path.is_dir()
        ]
        if len(self._recent_dirs) > MAX_RECENT_FILES:
            self._recent_dirs.pop()

    @property
    def recent_dirs(self) -> Iterator[Path]:
        """Return an iterator over the recent files, starting with the more recent one.

        The recent files list is updated first, removing invalid entries (deleted directories).
        """
        # Update recent files list.
        self._recent_dirs = [
            path
            for path in self._recent_dirs
            if path.is_dir() and path.resolve() != self.current_dir.resolve()
        ]
        return iter(self._recent_dirs)

    def _as_dict(self) -> dict[str, Any]:
        """Used for saving settings when closing application."""
        return {
            "recent_dirs": [str(path) for path in self.recent_dirs],
            "current_dir": str(self.current_dir),
        }

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> "Settings":
        recent_files = [Path(s) for s in d.get("recent_dirs", [])]
        current_directory = Path(d.get("current_dir", Path.cwd()))
        return Settings(
            _recent_dirs=recent_files,
            _current_dir=current_directory,
        )

    def save_settings(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings_data = self._as_dict()
        toml = dumps(settings_data)
        assert tomllib.loads(toml) == settings_data
        CONFIG_PATH.write_text(toml, "utf8")
        print(f"Config saved in {CONFIG_PATH}")

    @classmethod
    def load_settings(cls) -> "Settings":
        try:
            settings_dict = tomllib.loads(CONFIG_PATH.read_text("utf8"))
        except FileNotFoundError:
            settings_dict = {}
        except OSError as e:
            settings_dict = {}
            print(f"Enable to load settings: {e!r}")
        return cls._from_dict(settings_dict)
