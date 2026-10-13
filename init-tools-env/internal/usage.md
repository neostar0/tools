Usage: init-tools-env.sh [--check] [--force] [--remove] [BIN_DIR]

Create, refresh or remove the soft links that put this repo's tools on PATH:

  launch-qgc       -> qgc4-launch-with-logs/launch-qgc.sh
  close-qgc        -> close-qgc/close-qgc.sh
  format-md-table  -> md-table-aligner/format-md-table.sh
  build-qgc        -> qgc4-builder/build-linux.sh

BIN_DIR defaults to $HOME/.local/bin. Re-running is safe and idempotent.

Options:
  --check     report the link status without writing anything
  --force     replace a colliding file or a link that points elsewhere
  --remove    remove only the links that point into this repo (alias: --uninstall)
  -h, --help  show this message

Exit codes: 0 = every link is correct, created, or removed, 1 = a target is
missing, a link could not be written or removed, or --check found work to do,
2 = bad usage
