import tomllib
from enum import Enum, auto
from pathlib import Path
from typing import Any, Iterator, TypedDict

from tomli_w import dumps

from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from ptyx_mcq.scan import MCQPictureParser
from ptyx_mcq.scan.data.conflict_gestion import IntegrityChecker, DataChecker
from ptyx_mcq.scan.data.conflict_gestion.data_check.check import DataCheckResult
from ptyx_mcq.scan.data.conflict_gestion.integrity_check.check import IntegrityCheckResult
from ptyx_mcq_corrector.issues.issues_model import IssueInfo
from ptyx_mcq_corrector.param import CONFIG_PATH, MAX_RECENT_FILES


class ScanState(Enum):
    TO_DO = auto()
    IN_PROGRESS = auto()
    DONE = auto()


class Cache(TypedDict, total=False):
    parser: MCQPictureParser
    integrity_check: IntegrityCheckResult
    data_check: DataCheckResult


class InvalidFileError(OSError):
    """Error raised when the file type is invalid."""


class State:
    """The application current state.

    This includes recent files.
    """

    __curent_file: Path | None
    current_issue: IssueInfo | None
    scan_state: ScanState
    _cache: Cache

    def __init__(self, recent_files: list[Path] | None = None, current_file: Path | None = None):
        self._recent_files: list[Path] = recent_files or []
        self._reset_state()
        self._current_file = current_file

    def _reset_state(self) -> None:
        """
        Reset the state, except for the recent files list.
        """
        self._current_file = None
        self.current_issue = None
        self.scan_state = ScanState.TO_DO
        self._cache = Cache()

    @property
    def current_file_shortname(self) -> str:
        current_file = self._current_file
        return current_file.name[: -len(CONFIG_FILE_EXTENSION)] if current_file is not None else ""

    @property
    def parser(self) -> MCQPictureParser | None:
        if (current_file := self._current_file) is None:
            return None
        try:
            return self._cache["parser"]
        except KeyError:  # Update the parser.
            return self._cache.setdefault("parser", MCQPictureParser(current_file))

    @property
    def integrity_issues(self) -> None | IntegrityCheckResult:
        if self.scan_state != ScanState.DONE or (parser := self.parser) is None:
            return None
        try:
            return self._cache["integrity_check"]
        except KeyError:
            # Don't call IntegrityChecker(parser.scan_data).run() if the key exist
            return self._cache.setdefault("integrity_check", IntegrityChecker(parser.scan_data).run())

    @property
    def data_issues(self) -> None | DataCheckResult:
        if self.scan_state != ScanState.DONE or (parser := self.parser) is None:
            return None
        # Don't search for data issues if integrity issues has not been solved yet.
        if (issues := self.integrity_issues) is None or not issues.is_ok:
            return None
        try:
            return self._cache["data_check"]
        except KeyError:
            # Don't call IntegrityChecker(parser.scan_data).run() if the key exist
            return self._cache.setdefault("data_check", DataChecker(parser.scan_data).run())

    @property
    def integrity_issues_detected(self) -> bool:
        return (issues := self.integrity_issues) is not None and not issues.is_ok

    @property
    def data_issues_detected(self) -> bool:
        return (issues := self.data_issues) is not None and not issues.is_ok

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
        # Reset state, except for recent files list.
        self._reset_state()

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
