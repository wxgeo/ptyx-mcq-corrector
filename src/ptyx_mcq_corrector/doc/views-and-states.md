Notes on internal architecture
==============================

## States

When applying a complete documents' evaluation process, the application will be in those successive states:

- `NO_SCAN`
- `INTEGRITY_ISSUES_FOUND`
- `DATA_ISSUES_FOUND`
- `NO_ISSUES`
- `SCORES_COMPUTED`
- `CORRECTION_GENERATED`

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

_default view_: View.DEFAULT

### `DATA_ISSUES`

**Scan finished, not integrity issues found but data issues have yet to be solved now (incorrect names/ambiguous
answers)**

_default view_: View.DATA_ISSUES

### `NO_ISSUES`

**Scan finished, no issues left.**

_default view_: View.INTEGRITY_ISSUES

### `SCORES_COMPUTED`

**The score of each document has been computed.**

_default view_: View.SCORES

### `CORRECTION_GENERATED`

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
- `CORRECTION`

### `DEFAULT`

_possible states_: State.NO_SCAN

Available actions:

- scan (*)

(*): potentially slow action, that must take place in another thread

### `INTEGRITY_ISSUES`

_possible states_: State.INTEGRITY_ISSUES

Available actions:

- scan (*)
- fix (remove some documents)
- search and review

### `DATA_ISSUES`

_possible states_: State.DATA_ISSUES

Available actions:

- scan (*)
- fix (review + validate all, then refresh)
- search and review

### `SEARCH_RESULTS`

_possible states_: all except for State.NO_SCAN

Available actions:

- scan (*)
- modify (review + validate)
- escape: go back to default state's view
- search and review (new search)

### `SCORES`

_possible states_: State.SCORES_COMPUTED | State.CORRECTION_GENERATED

Available actions:

- scan (*)
- open spreadsheet
- generate correction (*)
- search and review

### `CORRECTION`

_possible states_: State.CORRECTION_GENERATED

Available actions:

- scan (*)
- go back to scores
- open spreadsheet
- see corrections
- open pdf
- regenerate correction? (*)
- search and review

------