# init-tools-env

Put this repo's command-line tools on `PATH` under short names by creating
soft links in a bin directory. Use it after cloning the repo or moving it,
so `launch-qgc`, `close-qgc`, `format-md-table` and `build-qgc` work from any
directory. `--remove` takes those links back out.

## Command Line

Linux/macOS only. Run from anywhere.

```bash
./init-tools-env/init-tools-env.sh              # links into ~/.local/bin
./init-tools-env/init-tools-env.sh --check      # report only, write nothing
./init-tools-env/init-tools-env.sh --force      # replace colliding links
./init-tools-env/init-tools-env.sh --remove     # remove the links it created
./init-tools-env/init-tools-env.sh /some/bin    # alternate bin directory
```

## Links created

| Name              | Target                                |
| ----------------- | ------------------------------------- |
| `launch-qgc`      | `qgc4-launch-with-logs/launch-qgc.sh` |
| `close-qgc`       | `close-qgc/close-qgc.sh`              |
| `format-md-table` | `md-table-aligner/format-md-table.sh` |
| `build-qgc`       | `qgc4-builder/build-linux.sh`         |

## Arguments and flags

| Flag/arg      | Default        | Effect                                    |
| ------------- | -------------- | ----------------------------------------- |
| `BIN_DIR`     | `~/.local/bin` | Directory the links are placed in         |
| `--check`     | off            | Report status only; writes nothing        |
| `--force`     | off            | Replace a colliding file or foreign link  |
| `--remove`    | off            | Remove only links pointing into this repo |
| `--uninstall` | off            | Alias for `--remove`                      |
| `--help`      | -              | Print the usage screen and exit           |

## Exit codes

`0` — every link is correct, created or removed; `1` — a target is missing, a
link could not be written or removed, or `--check` found missing/stale links;
`2` — bad usage.

## Requirements

Bash, on Linux/macOS. The bin directory must already be on `PATH`; this tool
does not edit your shell profile.

## Guarantees

- Idempotent: a second run reports `ok` for every link and changes nothing
- Links are absolute, so they resolve from any working directory
- Never overwrites a regular file or a link that points outside this repo
  unless `--force` is given
- `--remove` deletes only links that point into this repo; anything else in
  the bin directory is left untouched
- Makes sure each target script is executable
- `--check` writes nothing, so an agent can call it before acting
