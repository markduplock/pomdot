#!/usr/bin/env python3

import argparse
import datetime as dt
from pathlib import Path
import re
import sys
import time
import tomllib


DEFAULT_BAR_WIDTH = 30
MIN_BAR_WIDTH = 10
APP_NAME = "Pomdot"
APP_VERSION = "1.0"
BUILTIN_DEFAULT_TIME = ["30", "5", "0"]
BUILTIN_DEFAULT_COMPACT = False
BUILTIN_DEFAULT_NO_BELL = False
CONFIG_FILENAME = "config.toml"


def render_config_text(time_values: list[str], compact: bool, no_bell: bool, bar_width: int) -> str:
    compact_text = "true" if compact else "false"
    no_bell_text = "true" if no_bell else "false"

    return f"""# {APP_NAME} config file
# Default location: ~/.config/pomdot/{CONFIG_FILENAME}
# Command-line flags override these values.

# time = [FOCUS, REST, REPEAT]
# FOCUS and REST formats:
# - N  -> minutes
# - Nm -> minutes
# - Ns -> seconds
# - minimum value: 1
# - maximum value: none
# REPEAT format:
# - non-negative integer
# - minimum value: 0
# - maximum value: none
time = [\"{time_values[0]}\", \"{time_values[1]}\", \"{time_values[2]}\"]

# Compact output mode
# - expected values: true or false
compact = {compact_text}

# Disable completion bell
# - expected values: true or false
no_bell = {no_bell_text}

# Countdown bar width
# - expected value: integer
# - minimum value: {MIN_BAR_WIDTH}
# - maximum value: none
bar_width = {bar_width}
"""


def parse_duration(value: str) -> int:
    text = value.strip().lower()
    match = re.fullmatch(r"(\d+)([sm]?)", text)
    if not match:
        raise argparse.ArgumentTypeError(
            "invalid time format. Use N, Ns, or Nm (examples: 25, 25m, 1500s)."
        )

    amount = int(match.group(1))
    unit = match.group(2) or "m"

    if amount <= 0:
        raise argparse.ArgumentTypeError("time must be greater than zero.")

    if unit == "m":
        return amount * 60
    return amount


def format_hhmmss(seconds: int) -> str:
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def build_bar(remaining: int, total: int, width: int) -> str:
    ratio = remaining / total if total else 0
    filled = int(ratio * width)
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def parse_repeat(value: str) -> int:
    text = value.strip()
    if not re.fullmatch(r"\d+", text):
        raise argparse.ArgumentTypeError("repeat count must be a non-negative integer.")

    repeats = int(text)
    if repeats < 0:
        raise argparse.ArgumentTypeError("repeat count must be zero or greater.")
    return repeats


def parse_bar_width(value: str) -> int:
    text = value.strip()
    if not re.fullmatch(r"\d+", text):
        raise argparse.ArgumentTypeError("bar width must be an integer.")

    width = int(text)
    if width < MIN_BAR_WIDTH:
        raise argparse.ArgumentTypeError(
            f"bar width must be at least {MIN_BAR_WIDTH}."
        )
    return width


def default_config_path() -> Path:
    return Path.home() / ".config" / "pomdot" / CONFIG_FILENAME


def write_config(path: Path, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise FileExistsError(f"config file already exists: {path}")
    path.write_text(
        render_config_text(
            BUILTIN_DEFAULT_TIME,
            BUILTIN_DEFAULT_COMPACT,
            BUILTIN_DEFAULT_NO_BELL,
            DEFAULT_BAR_WIDTH,
        ),
        encoding="utf-8",
    )


def save_config(path: Path, time_values: list[str], compact: bool, no_bell: bool, bar_width: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_config_text(time_values, compact, no_bell, bar_width),
        encoding="utf-8",
    )


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        with path.open("rb") as file_obj:
            data = tomllib.load(file_obj)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"invalid TOML in config file {path}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"invalid config format in {path}: expected a table.")

    allowed_keys = {"time", "compact", "no_bell", "bar_width"}
    unknown_keys = [key for key in data.keys() if key not in allowed_keys]
    if unknown_keys:
        keys_text = ", ".join(sorted(unknown_keys))
        raise ValueError(f"unknown config key(s) in {path}: {keys_text}")

    validated = {}

    if "time" in data:
        time_value = data["time"]
        if not isinstance(time_value, list) or len(time_value) != 3:
            raise ValueError(
                f"invalid 'time' in {path}: expected an array with 3 values (focus, rest, repeat)."
            )

        normalized = []
        for item in time_value:
            if isinstance(item, (str, int)):
                normalized.append(str(item))
            else:
                raise ValueError(
                    f"invalid 'time' in {path}: each value must be a string or integer."
                )
        validated["time"] = normalized

    if "compact" in data:
        compact = data["compact"]
        if not isinstance(compact, bool):
            raise ValueError(f"invalid 'compact' in {path}: expected true or false.")
        validated["compact"] = compact

    if "no_bell" in data:
        no_bell = data["no_bell"]
        if not isinstance(no_bell, bool):
            raise ValueError(f"invalid 'no_bell' in {path}: expected true or false.")
        validated["no_bell"] = no_bell

    if "bar_width" in data:
        bar_width = data["bar_width"]
        if not isinstance(bar_width, int):
            raise ValueError(f"invalid 'bar_width' in {path}: expected an integer.")
        validated["bar_width"] = parse_bar_width(str(bar_width))

    return validated


def normalize_time_values(raw_time: list[str] | None, parser: argparse.ArgumentParser) -> list[str] | None:
    if raw_time is None:
        return None

    if len(raw_time) == 1 and "," in raw_time[0]:
        values = [part.strip() for part in raw_time[0].split(",")]
    else:
        values = [part.strip() for part in raw_time]

    if len(values) != 3 or any(value == "" for value in values):
        parser.error(
            "-t/--time must be either three values (FOCUS REST REPEAT) or one comma-separated value (FOCUS,REST,REPEAT)"
        )

    return values


def resolve_with_source(cli_value, config: dict, key: str, default_value):
    if cli_value is not None:
        return cli_value, "cli"
    if key in config:
        return config[key], "config"
    return default_value, "default"


def run_stage(
    stage_name: str,
    total_seconds: int,
    compact: bool,
    bar_width: int,
    ring_transition_bell: bool,
    is_last_stage: bool,
) -> None:
    start = dt.datetime.now()
    end = start + dt.timedelta(seconds=total_seconds)
    start_monotonic = time.monotonic()

    if compact:
        print()
    else:
        print(f"\nStage:     {stage_name}")
        print(f"Start:     {start.strftime('%H:%M:%S')}")
        print(f"End:       {end.strftime('%H:%M:%S')}")

    while True:
        elapsed = int(time.monotonic() - start_monotonic)
        remaining = max(0, total_seconds - elapsed)
        bar = build_bar(remaining, total_seconds, bar_width)
        line = f"Stage: {stage_name} | Remaining: {format_hhmmss(remaining)} {bar}"
        print(f"\r\033[2K{line}", end="", flush=True)

        if remaining == 0:
            if ring_transition_bell and not is_last_stage:
                print("\a", end="", flush=True)
            break
        time.sleep(1)

    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Pomdot terminal timer")
    parser.add_argument(
        "-t",
        "--time",
        nargs="+",
        metavar="TIME",
        default=None,
        help=(
            "timer config: FOCUS REST REPEAT. "
            "Accepts either '-t FOCUS REST REPEAT' or '-t FOCUS,REST,REPEAT'. "
            "FOCUS/REST use N, Ns, or Nm. REPEAT is a non-negative integer. "
            "Sequence ends on rest and runs one base focus/rest cycle plus REPEAT cycles. "
            "Default: 30 5 0"
        ),
    )
    parser.add_argument(
        "--compact",
        dest="compact",
        action="store_true",
        default=None,
        help="show only the live countdown line for each stage",
    )
    parser.add_argument(
        "--no-compact",
        dest="compact",
        action="store_false",
        help="disable compact output",
    )
    parser.add_argument(
        "--no-bell",
        dest="no_bell",
        action="store_true",
        default=None,
        help="disable bell sound when timer completes",
    )
    parser.add_argument(
        "--bell",
        dest="no_bell",
        action="store_false",
        help="enable bell sound when timer completes",
    )
    parser.add_argument(
        "--bar-width",
        type=parse_bar_width,
        default=None,
        metavar="WIDTH",
        help=f"countdown bar width (minimum {MIN_BAR_WIDTH}, default: {DEFAULT_BAR_WIDTH})",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="path to config file (default: ~/.config/pomdot/config.toml)",
    )
    parser.add_argument(
        "--write-config",
        action="store_true",
        help="write a starter config file and exit",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="show effective settings and their sources, then exit",
    )
    parser.add_argument(
        "--save-config",
        action="store_true",
        help="save effective timer settings to config and exit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing config when used with --write-config",
    )
    args = parser.parse_args()

    config_path = Path(args.config).expanduser() if args.config else default_config_path()
    cli_time_values = normalize_time_values(args.time, parser)

    if args.force and not args.write_config:
        parser.error("--force can only be used with --write-config")

    if args.write_config and args.save_config:
        parser.error("--write-config and --save-config cannot be used together")

    if args.status and args.write_config:
        parser.error("--status and --write-config cannot be used together")

    if args.status and args.save_config:
        parser.error("--status and --save-config cannot be used together")

    if args.write_config:
        if (
            cli_time_values is not None
            or args.compact is not None
            or args.no_bell is not None
            or args.bar_width is not None
        ):
            parser.error("--write-config cannot be combined with timer options")
        try:
            write_config(config_path, args.force)
        except FileExistsError as error:
            parser.error(str(error))
        print(f"Wrote config: {config_path}")
        return 0

    try:
        config = load_config(config_path)
    except ValueError as error:
        parser.error(str(error))

    if args.save_config:
        time_values = cli_time_values if cli_time_values is not None else BUILTIN_DEFAULT_TIME
        compact = args.compact if args.compact is not None else BUILTIN_DEFAULT_COMPACT
        no_bell = args.no_bell if args.no_bell is not None else BUILTIN_DEFAULT_NO_BELL
        bar_width = args.bar_width if args.bar_width is not None else DEFAULT_BAR_WIDTH
        sources = {
            "time": "cli" if cli_time_values is not None else "default",
            "compact": "cli" if args.compact is not None else "default",
            "no_bell": "cli" if args.no_bell is not None else "default",
            "bar_width": "cli" if args.bar_width is not None else "default",
        }
    else:
        time_values, time_source = resolve_with_source(
            cli_time_values,
            config,
            "time",
            BUILTIN_DEFAULT_TIME,
        )
        compact, compact_source = resolve_with_source(
            args.compact,
            config,
            "compact",
            BUILTIN_DEFAULT_COMPACT,
        )
        no_bell, no_bell_source = resolve_with_source(
            args.no_bell,
            config,
            "no_bell",
            BUILTIN_DEFAULT_NO_BELL,
        )
        bar_width, bar_width_source = resolve_with_source(
            args.bar_width,
            config,
            "bar_width",
            DEFAULT_BAR_WIDTH,
        )
        sources = {
            "time": time_source,
            "compact": compact_source,
            "no_bell": no_bell_source,
            "bar_width": bar_width_source,
        }

    try:
        focus_seconds = parse_duration(time_values[0])
        rest_seconds = parse_duration(time_values[1])
        repeats = parse_repeat(time_values[2])
        bar_width = parse_bar_width(str(bar_width))
    except argparse.ArgumentTypeError as error:
        parser.error(str(error))

    normalized_time_values = [str(time_values[0]).strip(), str(time_values[1]).strip(), str(time_values[2]).strip()]

    if args.status:
        print(f"{APP_NAME} v{APP_VERSION}")
        print(f"config_path = {config_path}")
        print(
            f"time = [\"{normalized_time_values[0]}\", \"{normalized_time_values[1]}\", \"{normalized_time_values[2]}\"] "
            f"(source: {sources['time']})"
        )
        print(f"compact = {'true' if compact else 'false'} (source: {sources['compact']})")
        print(f"no_bell = {'true' if no_bell else 'false'} (source: {sources['no_bell']})")
        print(f"bar_width = {bar_width} (source: {sources['bar_width']})")
        return 0

    if args.save_config:
        save_config(config_path, normalized_time_values, compact, no_bell, bar_width)
        print(f"Saved config: {config_path}")
        print(f"time = [\"{normalized_time_values[0]}\", \"{normalized_time_values[1]}\", \"{normalized_time_values[2]}\"]")
        print(f"compact = {'true' if compact else 'false'}")
        print(f"no_bell = {'true' if no_bell else 'false'}")
        print(f"bar_width = {bar_width}")
        return 0

    total_cycles = repeats + 1
    stages = []
    for cycle in range(1, total_cycles + 1):
        stages.append((f"Focus {cycle}/{total_cycles}", focus_seconds))
        stages.append((f"Rest {cycle}/{total_cycles}", rest_seconds))

    try:
        print(f"{APP_NAME} v{APP_VERSION}")
        print("\033[?25l", end="", flush=True)
        for index, (stage_name, stage_seconds) in enumerate(stages):
            run_stage(
                stage_name,
                stage_seconds,
                compact,
                bar_width,
                ring_transition_bell=not no_bell,
                is_last_stage=(index == len(stages) - 1),
            )
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    finally:
        print("\033[?25h", end="", flush=True)

    if no_bell:
        print("\nDone!")
    else:
        print("\nDone!\a")
    return 0


if __name__ == "__main__":
    sys.exit(main())
