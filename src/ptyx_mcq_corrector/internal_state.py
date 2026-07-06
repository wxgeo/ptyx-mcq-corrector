import tomllib
from enum import Enum, auto
from pathlib import Path
from typing import Any, Iterator

from tomli_w import dumps

from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from ptyx_mcq.scan import MCQPictureParser
from ptyx_mcq_corrector.param import CONFIG_PATH, MAX_RECENT_FILES


# class Action(Enum):
#     NONE = auto()
#     WORK_IN_PROGRESS = auto()
#     PENDING_REQUEST = auto()
#     DISPLAY_RESULTS = auto()


# class Step(Enum):
#     NO_FILE = auto()
#     FILE_SELECTED = auto()
#     SCAN_IN_PROGRESS = auto()
#     SCAN_FINISHED = auto()
#     ISSUES_FIXED = auto()


class ScanState(Enum):
    TO_DO = auto()
    IN_PROGRESS = auto()
    DONE = auto()


class InvalidFileError(OSError):
    """Error raised when the file type is invalid."""


class State:
    """The application current state.

    This includes recent files.
    """

    def __init__(self, recent_files: list[Path] | None = None, current_file: Path | None = None):
        self._recent_files: list[Path] = recent_files or []
        self._current_file: Path | None = current_file
        self._parser: MCQPictureParser | None = None
        self.scan_state: ScanState = ScanState.TO_DO

    # @property
    # def step(self) -> Step:
    #     if self.current_file is None:
    #         return Step.NO_FILE
    #     if self._scan_state = UNDONE

    @property
    def parser(self) -> MCQPictureParser | None:
        current_file = self._current_file
        if current_file is None:
            self._parser = None
        elif (
            self._parser is None
            or self._parser.scan_data.paths.configfile.resolve() != current_file.resolve()
        ):
            # Update the parser.
            self._parser = MCQPictureParser(current_file)
        return self._parser

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
        elif self._current_file is not None and config_file.resolve() == self._current_file.resolve():
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
        self._current_file = None

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
        current_file = self.current_file
        self._recent_files = [
            path
            for path in self._recent_files
            if path.is_file() and (current_file is None or path.resolve() != current_file.resolve())
        ]
        return iter(self._recent_files)

    def _as_dict(self) -> dict[str, Any]:
        """Used for saving state when closing application."""
        d: dict[str, Any] = {"recent_files": [str(path) for path in self.recent_files]}
        if self.current_file is not None:
            d["current_file"] = str(self.current_file)
        return d

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> "State":
        recent_files = [Path(s) for s in d.get("recent_files", [])]
        current_file = d.get("current_file")
        if current_file is not None:
            # noinspection PyTypeChecker
            current_file = Path(current_file)
        return State(
            recent_files=recent_files,
            current_file=current_file,
        )

    def save(self) -> None:
        """Save configuration."""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings_data = self._as_dict()
        toml = dumps(settings_data)
        assert tomllib.loads(toml) == settings_data
        CONFIG_PATH.write_text(toml, "utf8")
        print(f"Config saved in {CONFIG_PATH}")

    @classmethod
    def load(cls) -> "State":
        """Load configuration."""
        try:
            settings_dict = tomllib.loads(CONFIG_PATH.read_text("utf8"))
        except FileNotFoundError:
            settings_dict = {}
        except OSError as e:
            settings_dict = {}
            print(f"Enable to load state: {e!r}")
        return cls._from_dict(settings_dict)
