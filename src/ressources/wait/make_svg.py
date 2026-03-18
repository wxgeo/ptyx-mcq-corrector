import re
from pathlib import Path

DIR = Path(__file__).parent

STEP = 10  # 255 / 24 ~ 10


def create_svg(i: int) -> None:
    svg = (DIR / "wait.svg").read_text()

    n = i * STEP

    def f(m: re.Match) -> str:
        nonlocal n
        code = f"fill:#{n:02X}{n:02X}{n:02X}"
        n = (n - STEP) % 240
        return code

    (DIR / f"wait-{i}.svg").write_text(re.sub("fill:#000000", f, svg))


def main():
    for i in range(24):
        create_svg(i)


if __name__ == "__main__":
    main()
