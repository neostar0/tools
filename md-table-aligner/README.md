# Markdown Table Aligner

Lines up the columns of markdown tables so they stay readable in plain
text, including Chinese/CJK content. Use when markdown tables look ragged
in raw text, when asked to align/format/tidy/fix markdown tables, or before
committing documentation. Writes a timestamped copy next to the source and
leaves the original untouched unless `--in-place` is given.

## Drag & Drop (Windows)

Drag a `.md` file onto `drop-md-file-here.cmd` — the aligned copy appears
next to it (`FILE_2026-1002-1058.md`); the original is not modified.

## Command Line

Run from this folder. `python3` may be spelled `python` on Windows.

```bash
python3 internal/fmt_md_tables.py --check FILE.md   # report only, writes nothing
python3 internal/fmt_md_tables.py FILE.md           # -> FILE_2026-1002-1058.md
python3 internal/fmt_md_tables.py --in-place FILE.md
python3 internal/fmt_md_tables.py --output DIR FILE.md
```

```bash
./format-md-table.sh --check FILE.md   # same tool, no python3 prefix
```

## Options

| Flag            | Effect                                  |
| --------------- | --------------------------------------- |
| `--check`       | Report misaligned tables, write nothing |
| `--in-place`    | Overwrite the inputs instead            |
| `--suffix TEXT` | Replace the default suffix              |
| `--output DIR`  | Write outputs to `DIR`                  |

## Exit codes

`0` on success, `1` if a table is misaligned under `--check` or a file
cannot be read or written.

## Guarantees

Only blocks that contain a separator row are treated as tables, and fenced
code blocks are skipped, so pipes in prose and tables in code samples are
left alone. Output is idempotent and preserves CRLF or LF line endings.

Read `internal/NOTES.md` only if the output looks wrong or you need to
change the script.
