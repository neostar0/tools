# Developer notes

Design decisions, edge cases and how to work on this tool. User facing
documentation is in `../README.md`.

## Layout

| File                    | Role                                              |
| ----------------------- | ------------------------------------------------- |
| `fmt_md_tables.py`      | The whole implementation, standard library only   |
| `test_fmt_md_tables.py` | Regression tests, `unittest`, no third party deps |
| `NOTES.md`              | This file                                         |

## Run the tests

```bash
python3 internal/test_fmt_md_tables.py              # from the package folder
python3 -m unittest discover internal -v            # from the package folder
python3 -m unittest discover md-table-aligner/internal -v   # from the repo root
```

Add a case to `test_fmt_md_tables.py` whenever a behaviour is added or an edge
case is found. `test_idempotent_is_required` and `test_aligned_width_is_uniform`
are applied to every sample, so a new sample only needs its own assertions.

## How table detection works

`iter_blocks` walks the lines and yields either a single plain line or a run of
consecutive lines starting with `|`. Code fences (```` ``` ```` or `~~~`) flip
an `in_fence` flag and their lines are always yielded as plain.

`format_table` then refuses to touch a block unless it contains a separator row
(matching `^:?-+:?$`). This is what keeps a stray `| ... |` line inside prose
from being reformatted into a table header.

A block without a separator row is therefore returned unchanged, which also
means headerless tables are never rewritten.

## Width measurement

`display_width` walks the characters and uses `unicodedata.east_asian_width`,
counting `W` and `F` as 2 columns and skipping combining marks. `cell_width`
subtracts one per `\|` so an escaped pipe counts as the single character it
renders as.

`rendered_width` is the same idea applied to a whole line, used by `check`.

## Alignment algorithm

1. Drop the outer pipes from a row, then split on unescaped `|` and trim cells.
   Splitting first and trimming afterwards would produce two spurious empty
   cells per row.
2. Compute the maximum rendered width per column over the data rows. The
   separator row is excluded, since its dashes are not content. Every
   column is floored at 1, so an all-empty column still gets a one-dash
   separator row and the output stays `--check`-clean.
3. Add one or two columns to any column whose marker carries a leading or
   trailing colon, so the marker fits inside the padded column.
4. Emit each row padded to the column width, and the separator after the first
   row.

## Known limitations

- A line longer than one terminal row obviously wraps, but the table is still
  aligned by source column.
- Nesting a table inside a list item or blockquote is not detected, because the
  blockquote or list marker means the line does not start with `|`.
- Only `| --- |` style separators are recognised, never a row of dashes without
  the outer pipes.
- Column widths are computed per table, so two adjacent tables with different
  content are not aligned to a shared grid.

## Invariants to preserve when editing

- The input file is never modified unless `--in-place` is passed.
- Running the formatter twice yields byte identical output.
- CRLF input produces CRLF output, LF input produces LF output.
- A single invocation uses one timestamp for every file it processes.
- Read and write failures are reported as one line to stderr, never a
  traceback, because the batch file surfaces that text to a non technical user.
