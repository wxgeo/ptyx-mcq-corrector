Notes on internal architecture
==============================

## States

When applying a complete documents' evaluation process, the application will be in those successive states:

- `NO_SCAN`
- `SCAN_IN_PROGRESS`
- `INTEGRITY_ISSUES`
- `DATA_ISSUES`
- `VALIDATED`
- `SCORES_COMPUTED`
- `CORRECTIONS_GENERATED`

Not decided yet: add something like `CORRECTIONS_IN_PROGRESS`,
with the ability to abort the PDF files' generation?

### `NO_SCAN`

**No scan done yet.**

_default view_: View.DEFAULT

Two subcases can be distinguished, by testing if `AppState.current_file is None`:

* no file selected yet
* file selected, but no scan process was launched

### `SCAN_IN_PROGRESS`

**scan process is running**

_default view_: View.DEFAULT

### `INTEGRITY_ISSUES`

**Scan finished, integrity issues have been found (missing pages/duplicate pages)**

_default view_: View.INTEGRITY_ISSUES

### `DATA_ISSUES`

**Scan finished, not integrity issues found but data issues have yet to be solved now (incorrect names/ambiguous
answers)**

_default view_: View.DATA_ISSUES

### `VALIDATED`

**Scan finished, no issues left.**

_default view_: View.SCORES

### `SCORES_COMPUTED`

**The score of each document has been computed.**

_default view_: View.SCORES

### `CORRECTIONS_GENERATED`

**The correction version in pdf have been generated for each document.**

_default view_: View.CORRECTION



------------
Notes:

Each state's default view must be stored in a dict `main_area.DEFAULT_VIEWS`.

New state must be set via `EventsHandler.set_state()`, which must:

- update the state in `AppState.state`.
- change the view to the state's default view

------------

## Views

Instances of IntEnum.

Each view corresponds to an index of the application main StackedWidget.

Changing the view takes place in `MainArea.set_view()`, which must start with an assertion to verify that the
`AppState.state` is compatible.

Defined views:

- `DEFAULT`
- `INTEGRITY_ISSUES`
- `DATA_ISSUES`
- `SEARCH_RESULTS`
- `SCORES`
- `CORRECTIONS`

### `DEFAULT`

_possible states_: State.NO_SCAN

Available actions:

- scan (*) -> (1)

(*): potentially slow action, that must take place in another thread
(1): State.INTEGRITY_ISSUE | State.DATA_ISSUE | State.VALIDATED

### `INTEGRITY_ISSUES`

_possible states_: State.INTEGRITY_ISSUES

Available actions:

- scan (*) -> (1)
- fix if possible (remove some documents) -> State.DATA_ISSUES | State.VALIDATED

### `DATA_ISSUES`

_possible states_: State.DATA_ISSUES

Available actions:

- scan (*) -> (1)
- fix (review + validate all, then refresh) -> State.DATA_ISSUES | State.VALIDATED
- search and review -> <state unchanged>

### `SEARCH_RESULTS`

_possible states_: all except for State.NO_SCAN and State.SCAN_IN_PROGRESS

Available actions:

- scan (*) -> (1)
- modify (review + validate) -> State.DATA_ISSUES | State.VALIDATED
- escape: go back to default state's view -> <state unchanged>
- search and review (new search) -> <state unchanged>

### `SCORES`

_possible states_: State.SCORES_COMPUTED | State.CORRECTIONS_GENERATED

Available actions:

- scan (*) -> (1)
- open spreadsheet -> <state unchanged>
- generate correction (*) -> State.CORRECTIONS_GENERATED
- search and review -> <state unchanged>

### `CORRECTIONS`

_possible states_: State.CORRECTIONS_GENERATED

Available actions:

- scan (*) -> (1)
- go back to scores -> States.SCORES_COMPUTED
- open spreadsheet -> <state unchanged>
- see corrections -> <state unchanged>
- open pdf -> <state unchanged>
- regenerate correction? (*) -> <state unchanged>
- search and review -> <state unchanged>

------