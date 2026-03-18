project := "ptyx_mcq_corrector"

import "../justfile"
import "../justfiles/ui.just"

doc:
    @cd ".." && just doc {{project}}
ruff:
    @cd ".." && just ruff {{project}}
mypy:
    @cd ".." && just mypy {{project}}
pytest:
    @cd ".." && just pytest {{project}}
fix:
    @cd ".." && just fix {{project}}
test:
    @cd ".." && just test {{project}}
push:
    @cd ".." && just push {{project}}
build:
    @cd ".." && just build {{project}}
release:
    @cd ".." && just release {{project}}
ui:
    @cd ".." && just ui {{project}}