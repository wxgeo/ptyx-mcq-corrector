from functools import wraps
from typing import Protocol, Callable, TYPE_CHECKING

from ptyx_mcq_corrector import param

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow


class HasMainWindow(Protocol):
    main_window: "McqCorrectorMainWindow"


def update_ui(f: Callable[..., bool]) -> Callable[..., bool]:
    """Decorator used to indicate that UI must be updated if the operation was successful.

    The decorated function must return True if the operation was successful, False else.

    When nested operations are performed, intermediate ui updates are prevented by
    freezing temporally the user interface, then updating it only once the last operation is performed.
    """

    @wraps(f)
    def wrapper(self: HasMainWindow, *args, **kw) -> bool:
        current_freeze_value = self.main_window.freeze_update_ui
        self.main_window.freeze_update_ui = True
        if not param.DEBUG:
            self.main_window.setUpdatesEnabled(False)
        try:
            if param.DEBUG:
                _args = [repr(arg) for arg in args] + [f"{key}={val!r}" for (key, val) in kw.items()]
                print(f"{f.__name__}({', '.join(_args)})")
            else:
                print(f.__name__)
            update = f(self, *args, **kw)
            assert isinstance(update, bool), (
                f"Method `{self.__class__.__name__}.{f.__name__}` must return a boolean, not {update!r}"
            )
            if update and not current_freeze_value:
                self.main_window.update_ui()
            return update
        finally:
            self.main_window.setUpdatesEnabled(True)
            self.main_window.freeze_update_ui = current_freeze_value

    return wrapper
