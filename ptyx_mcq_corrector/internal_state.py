import tomllib
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Iterator

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
    current_directory: Path | None = None
    current_action: CurrentAction|None = None
    current_picture: Path|None = None
    checkable_areas: list[tuple] = field(default_factory=list)


    @property
    def default_directory(self) -> Path:
        """Default directory proposed when opening a file.

        This is the folder containing the current file, if saved on disk.
        Else, it is last used directory.
        """
        if self.current_doc_path is None:
            return self._current_directory if self._current_directory is not None else Path.cwd()
        return self.current_doc_path.parent

    @current_directory.setter
    def current_directory(self, path: Path) -> None:
        self._current_directory = path



    @property
    def current_doc_path(self) -> Path | None:
        return None if self.current_doc is None else self.current_doc.path

    # @property
    # def current_doc_directory(self) -> Path | None:
    #     return None if self.current_doc_path is None else self.current_doc_path.parent






    def open_dir(self, path: Path):
        # Attention, paths must be resolved to don't miss duplicates (symlinks...)!
        # Do nothing if it's the current directory.
        if path.resolve() != self.current_doc_path:
            self.close_dir()
            self.current_

    def close_doc(self, side: Side = None, index: int = None) -> Path | None:
        if side is None:
            side = self._current_side
        path = self.docs(side).close_doc(index)
        if path is not None and path.is_file():
            self._remember_file(path)
        return path

    def _remember_file(self, new_path: Path) -> None:
        # The same file must not appear twice in the list.
        self._recent_dirs = [new_path] + [
            path for path in self._recent_dirs if path.resolve() != new_path.resolve() and path.is_file()
        ]
        if len(self._recent_dirs) > MAX_RECENT_FILES:
            self._recent_dirs.pop()



    @property
    def recent_files(self) -> Iterator[Path]:
        """Return an iterator over the recent files, starting with the more recent one.

        The recent files list is updated first, removing invalid entries (deleted files).
        """
        # Update recent files list.
        opened_files = self.opened_files
        self._recent_dirs = [
            path for path in self._recent_dirs if path.is_file() and path not in opened_files
        ]

        return iter(self._recent_dirs)

    # @property
    # def current_doc_is_saved(self) -> bool:
    #     if self.current_doc is None:
    #         return True
    #     return self.current_doc.is_saved

    # @property
    # def current_doc_title(self) -> str:
    #     if self.current_doc is None:
    #         return ""
    #     return self.current_doc.title

    def _as_dict(self) -> dict[str, Any]:
        """Used for saving settings when closing application."""
        return {
            "current_side": self._current_side.name,
            "recent_files": [str(path) for path in self.recent_files],
            "docs": {"left": self._left_docs.as_dict(), "right": self._right_docs.as_dict()},
            "current_directory": str(self.current_directory),
        }

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> "Settings":
        recent_files = [Path(s) for s in d.get("recent_files", [])]
        current_side = getattr(Side, d.get("current_side", "LEFT"), Side.LEFT)
        current_directory = Path(d.get("current_directory", Path.cwd()))
        docs = {
            side: DocumentsCollection(
                _side=side,
                _documents=[Document(Path(path)) for path in data.get("files", []) if Path(path).is_file()],
                _current_index=data.get("current_index", 0),
            )
            for (side, data) in d.get("docs", {}).items()
        }
        return Settings(
            _recent_dirs=recent_files,
            _current_side=current_side,
            _left_docs=docs.get("left", DocumentsCollection(Side.LEFT)),
            _right_docs=docs.get("right", DocumentsCollection(Side.RIGHT)),
            _current_directory=current_directory,
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
