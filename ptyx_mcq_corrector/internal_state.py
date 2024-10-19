import tomllib
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Iterator, Any, Self

from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from tomli_w import dumps

from ptyx_mcq_corrector.param import CONFIG_PATH, MAX_RECENT_FILES


class Action(Enum):
    NONE = auto()
    IN_PROGRESS = auto()
    MISSING_NAME = auto()
    DUPLICATE_PAGES = auto()
    DUPLICATE_NAMES = auto()
    ANSWERS_REVIEW = auto()
    MISSING_PAGES = auto()
    RESULTS = auto()


class InvalidFileError(OSError):
    """Error raised when the file type is invalid."""


@dataclass(kw_only=True)
class State:
    """The application current state.

    This includes recent files.
    """

    _recent_files: list[Path] = field(default_factory=list)
    _current_file: Path | None = None
    current_action: Action = Action.NONE
    current_picture: Path | None = None
    clickable_areas: list[tuple] = field(default_factory=list)

    @property
    def default_dir(self) -> Path:
        """Default directory proposed when opening a file.

        This is the folder containing the current file, if saved on disk.
        Else, it is last used directory.
        """
        return self._current_file.parent if self._current_file is not None else Path.cwd()

    @property
    def current_file(self) -> Path | None:
        return self._current_file

    def open_file(self, config_file: Path) -> bool:
        """Open a ptyx configuration file.

        Before opening, verification occurs:
        - `config_file` must be an existing file.
        - it must have the correct extension (i.e. `.ptyx.mcq.config.json`).

        Return a boolean, indicating if the current directory was effectively changed."""
        # Attention, paths must be resolved to don't miss duplicates (symlinks...)!
        # Do nothing if it's the current directory.
        if not config_file.is_file():
            raise FileNotFoundError(f"File '{config_file}' does not exist.")
        elif config_file.resolve() == self._current_file.resolve():
            print(f"File '{config_file.name}' already opened.")
            return False
        elif not config_file.name.endswith(CONFIG_FILE_EXTENSION):
            raise InvalidFileError(f"Invalid file type: '{config_file.name}'.")
        self.close_file()
        self._current_file = config_file
        return True

    def close_file(self) -> None:
        if self._current_file is not None:
            self._remember_file(self._current_file)
        # Reset state, except for recent directories list.
        self.current_action = Action.NONE
        self.current_picture = None
        self._current_file = None
        self.clickable_areas = []

    def _remember_file(self, new_path: Path) -> None:
        # The same file must not appear twice in the list.
        self._recent_files = [new_path] + [
            path for path in self._recent_files if path.resolve() != new_path.resolve() and path.is_dir()
        ]
        if len(self._recent_files) > MAX_RECENT_FILES:
            self._recent_files.pop()

    @property
    def recent_files(self) -> Iterator[Path]:
        """Return an iterator over the recent files, starting with the more recent one.

        The recent files list is updated first, removing invalid entries (deleted directories).
        """
        # Update recent files list.
        self._recent_files = [
            path
            for path in self._recent_files
            if path.is_dir() and path.resolve() != self.current_file.resolve()
        ]
        return iter(self._recent_files)

    def _as_dict(self) -> dict[str, Any]:
        """Used for saving state when closing application."""
        return {
            "recent_files": [str(path) for path in self.recent_files],
            "current_file": str(self.current_file),
        }

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> Self:
        recent_files = [Path(s) for s in d.get("recent_files", [])]
        current_file = Path(d.get("current_file", Path.cwd()))
        return State(
            _recent_files=recent_files,
            _current_file=current_file,
        )

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings_data = self._as_dict()
        toml = dumps(settings_data)
        assert tomllib.loads(toml) == settings_data
        CONFIG_PATH.write_text(toml, "utf8")
        print(f"Config saved in {CONFIG_PATH}")

    @classmethod
    def load(cls) -> Self:
        try:
            settings_dict = tomllib.loads(CONFIG_PATH.read_text("utf8"))
        except FileNotFoundError:
            settings_dict = {}
        except OSError as e:
            settings_dict = {}
            print(f"Enable to load state: {e!r}")
        return cls._from_dict(settings_dict)
