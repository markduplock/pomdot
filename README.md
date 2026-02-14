# Pomdot

Pomdot is a minimal terminal with support for focus / rest / repeat timers and user configs.

Current version: `1.0`

## Requirements

- Should work on most Linux systems
- Python 3.11+
- Terminal with ANSI escape support

## Run

```bash
python3 pomdot.py
```

Or make it executable and run directly:

```bash
chmod +x pomdot.py
./pomdot.py
```

## Usage

```bash
python3 pomdot.py [-t FOCUS REST REPEAT|FOCUS,REST,REPEAT] [--compact|--no-compact] [--no-bell|--bell] [--bar-width WIDTH] [--config PATH] [--status]
python3 pomdot.py --write-config [--config PATH] [--force]
python3 pomdot.py [timer options] --save-config [--config PATH]
```

- `-t FOCUS REST REPEAT`
  - or comma form: `-t FOCUS,REST,REPEAT`
  - `FOCUS` and `REST` support `N`, `Nm`, or `Ns`
  - plain `N` is minutes
  - `REPEAT` is a non-negative integer
  - default is `30 5 0`
  - sequence runs one base `Focus -> Rest` cycle, then `REPEAT` additional cycles
  - timer always ends on `Rest`
- `--compact`
  - shows only the live countdown line for each stage
- `--no-compact`
  - forces non-compact output (useful to override config)
- `--no-bell`
  - disables all terminal bells (stage transitions and completion)
- `--bell`
  - enables terminal bells (stage transitions and completion)
- `--bar-width WIDTH`
  - sets countdown bar width
  - minimum `10`, default `30`
- `--config PATH`
  - uses a custom config file path
  - default path is `~/.config/pomdot/config.toml`
- `--write-config`
  - writes a starter config file and exits
- `--save-config`
  - saves resolved timer settings to config and exits
  - does not run the timer
  - unspecified options use built-in defaults (not current config values)
- `--status`
  - prints effective settings and exits
  - includes value source labels: `cli`, `config`, or `default`
- `--force`
  - used with `--write-config` to overwrite an existing config file

## Config file

Pomdot loads defaults from `~/.config/pomdot/config.toml` when present.

Precedence order:

1. CLI options
2. Config file values
3. Built-in defaults

Invalid config values cause Pomdot to exit with an error.

Generate a starter config:

```bash
python3 pomdot.py --write-config
```

Overwrite an existing config:

```bash
python3 pomdot.py --write-config --force
```

Example config:

```toml
# Pomdot config file
# Default location: ~/.config/pomdot/config.toml
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
time = ["30", "5", "0"]

# Compact output mode
# - expected values: true or false
compact = false

# Disable completion bell
# - expected values: true or false
no_bell = false

# Countdown bar width
# - expected value: integer
# - minimum value: 10
# - maximum value: none
bar_width = 30
```

## Examples

```bash
# Default run
python3 pomdot.py

# 25-minute focus, 5-minute rest, no extra cycles
python3 pomdot.py -t 25 5 0

# 2 cycles total (base + 1 repeat), compact mode, no bell
python3 pomdot.py -t 25m 5m 1 --compact --no-bell

# Override a config that has compact/no_bell enabled
python3 pomdot.py --no-compact --bell

# Second-based quick test with wider bar
python3 pomdot.py -t 10s 5s 0 --bar-width 40

# Use custom config file
python3 pomdot.py --config ~/my-pomdot.toml

# Write starter config to default path
python3 pomdot.py --write-config

# Save current command options as new defaults and exit
python3 pomdot.py -t 20,2,2 --no-bell --bar-width 20 --save-config

# Print effective settings with source labels and exit
python3 pomdot.py --status

# Status with CLI overrides
python3 pomdot.py -t 20,2,2 --no-bell --status
```
