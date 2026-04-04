"""Interactive terminal prompts for MA assignment and live-order confirmation."""
from __future__ import annotations

from typing import Callable, List, Sequence, Tuple

MaOption = Tuple[str, int, str]


def build_ma_assignment_options(
    lengths: Sequence[int] | None = None,
    timeframes: Sequence[str] | None = None,
) -> List[MaOption]:
    lengths = list(lengths or [5, 10, 20, 50, 100, 150, 200])
    timeframes = list(timeframes or ["1H", "D"])
    options: List[MaOption] = []
    for ln in lengths:
        for tf in timeframes:
            options.append(("SMA", ln, tf))
            options.append(("EMA", ln, tf))
    return options


def default_ma_selection_index(
    options: Sequence[MaOption],
    default: MaOption = ("SMA", 50, "1H"),
) -> int:
    """Return 1-based index into ``options`` for menu default."""
    try:
        return list(options).index(tuple(default)) + 1
    except ValueError:
        return 1


def print_ma_assignment_menu(options: Sequence[MaOption], default_idx: int) -> None:
    """Print two-column numbered MA choices (SMA left, EMA right per row)."""
    for j in range(0, len(options), 2):
        left_num = j + 1
        right_num = j + 2
        fam_l, ln_l, tf_l = options[j]
        if j + 1 < len(options):
            fam_r, ln_r, tf_r = options[j + 1]
            left_label = f"{fam_l} {ln_l} {tf_l}"
            right_label = f"{fam_r} {ln_r} {tf_r}"
            print(f" {left_num:3d}) {left_label:16s} {right_num:3d}) {right_label}")
        else:
            left_label = f"{fam_l} {ln_l} {tf_l}"
            print(f" {left_num:3d}) {left_label:16s}")


def read_ma_selection(
    options: Sequence[MaOption],
    default_idx: int,
    *,
    reader: Callable[[str], str] | None = None,
) -> MaOption:
    """Read a menu choice; invalid or empty input falls back to ``default_idx`` (1-based)."""
    _input = reader if reader is not None else input
    sel = _input(f"Selection [default {default_idx}]: ").strip()
    if not sel:
        sel_idx = default_idx
    else:
        try:
            sel_idx = int(sel)
        except Exception:
            sel_idx = default_idx
    if sel_idx < 1 or sel_idx > len(options):
        sel_idx = default_idx
    return options[sel_idx - 1]


def prompt_ma_assignment(
    ticker: str,
    *,
    options: Sequence[MaOption] | None = None,
    reader: Callable[[str], str] | None = None,
) -> MaOption:
    """Prompt for MA type, length, and timeframe for one ticker.

    ``reader`` defaults to :func:`input`; inject a callable for tests or scripting.
    """
    opts = list(options or build_ma_assignment_options())
    default_idx = default_ma_selection_index(opts)
    print(
        f"\nAssign MA for {ticker}. Choose from the numbered list below "
        f"(enter number, default {default_idx}):"
    )
    print_ma_assignment_menu(opts, default_idx)
    return read_ma_selection(opts, default_idx, reader=reader)


def confirm_live_transmit(
    *,
    assume_yes: bool = False,
    reader: Callable[[str], str] | None = None,
) -> bool:
    """Return True if the user confirms live transmission (types ``YES``), or if ``assume_yes``."""
    if assume_yes:
        return True
    _input = reader if reader is not None else input
    confirm = _input("CONFIRM transmit live orders now? Type YES to proceed: ").strip()
    return confirm == "YES"
