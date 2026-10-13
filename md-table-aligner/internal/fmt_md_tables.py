#!/usr/bin/env python3
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Aligns the columns of every markdown table in the given files.

Cells are padded to the width of the widest cell in their column so that a
table stays readable when the file is opened as plain text. Widths are
measured in terminal columns: East Asian wide and fullwidth characters count
as two, combining marks count as zero.

Fenced code blocks are left untouched, and the alignment markers (``:---``)
of a separator row are preserved.

The input files are never modified: a stamped copy is written next to each
one, for example ``report.md`` becomes ``report_2026-1002-1058.md``. Use
``--in-place`` to overwrite the inputs instead, which is handy for CI.

Usage:
    fmt_md_tables.py FILE [FILE ...]          write stamped copies of FILE
    fmt_md_tables.py --check FILE [FILE ...]  report misaligned tables only

Options:
    --in-place        overwrite the input files
    --suffix TEXT     suffix for the output name, default _YYYY-MMDD-HHMM
    --output DIR      directory for the output files
"""

import argparse
import datetime
import os
import re
import sys
import unicodedata

# Suffix appended to the output file when it is not written in place.
DEFAULT_SUFFIX = datetime.datetime.now().strftime("_%Y-%m%d-%H%M")

# A separator cell is made of dashes with optional leading/trailing colons.
SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")

# A table row starts with a pipe after optional leading whitespace.
ROW_RE = re.compile(r"^\s*\|")

# A code fence opens or closes with three or more backticks or tildes.
FENCE_RE = re.compile(r"^\s*(?:```+|~~~+)")

# An escaped pipe inside a cell does not act as a cell separator.
ESCAPED_PIPE_RE = re.compile(r"(?<!\\)\|")

# What iter_blocks yields for a line that is not part of a table.
PLAIN = "plain"
TABLE = "table"


def display_width(text):
    """Return the number of terminal columns `text` occupies."""
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def rendered_width(cell):
    """Return the rendered width of a cell, ignoring `\\|` escape markers."""
    return display_width(cell) - cell.count("\\|")


def pad(text, width):
    """Pad `text` on the right so that it occupies `width` terminal columns."""
    return text + " " * max(0, width - rendered_width(text))


def split_row(line):
    """Split a table row into its trimmed cell contents."""
    text = line.strip()
    # Drop the outer pipes before splitting, otherwise they yield empty cells.
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    return [cell.strip() for cell in ESCAPED_PIPE_RE.split(text)]


def is_separator(cells):
    """Return True when every cell of the row is a horizontal rule."""
    return bool(cells) and all(SEPARATOR_CELL_RE.match(cell) for cell in cells)


def separator_cell(width, marker):
    """Build a separator cell, plus the extra width its colons add."""
    dashes = "-" * max(width, 1)
    lead = marker.startswith(":")
    trail = marker.endswith(":")
    return (":" if lead else "") + dashes + (":" if trail else ""), lead + trail

def split_lines(text):
    """Split `text` on newline only, without breaking on exotic line marks.

    `str.splitlines()` also splits on \\v, \\f, U+2028 and friends, which
    would silently turn them into real newlines when the result is joined
    back. A final newline is dropped because `process`/`check` re-add it.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def iter_blocks(lines):
    """Yield (kind, payload) chunks of `lines`, tables are grouped together.

    `kind` is TABLE for a list of row lines, otherwise PLAIN for a single line.
    Fenced code blocks are always reported as PLAIN.
    """
    in_fence = False
    index = 0

    while index < len(lines):
        if FENCE_RE.match(lines[index]):
            in_fence = not in_fence
            yield PLAIN, lines[index]
            index += 1
            continue

        if not in_fence and ROW_RE.match(lines[index]):
            start = index
            while index < len(lines) and not in_fence and ROW_RE.match(lines[index]):
                index += 1
            yield TABLE, lines[start:index]
            continue

        yield PLAIN, lines[index]
        index += 1


def format_table(block):
    """Return the aligned rendering of the table rows in `block`."""
    rows = []
    markers = None
    for line in block:
        cells = split_row(line)
        if is_separator(cells):
            markers = cells
            continue
        rows.append(cells)

    if not rows:
        return list(block)

    # Without a separator row the block is not a markdown table, leave it alone.
    if markers is None:
        return list(block)

    column_count = max(len(cells) for cells in rows)
    widths = [0] * column_count
    for cells in rows:
        for index, cell in enumerate(cells):
            widths[index] = max(widths[index], rendered_width(cell))

    # An all-empty column still needs one dash, so its separator row and
    # its data rows end up the same width (otherwise --check rejects our
    # own output).
    widths = [max(width, 1) for width in widths]

    # A table may declare more separator cells than it has data columns.
    markers = list(markers) + ["-"] * (column_count - len(markers))

    # Alignment colons sit outside the padding, so those columns are wider.
    rule_cells = [separator_cell(widths[i], markers[i]) for i in range(column_count)]
    column_widths = [widths[i] + rule_cells[i][1] for i in range(column_count)]

    out = []
    for position, cells in enumerate(rows):
        cells = list(cells) + [""] * (column_count - len(cells))
        out.append("| " + " | ".join(pad(cell, column_widths[i]) for i, cell in enumerate(cells)) + " |")
        if position == 0:
            out.append("| " + " | ".join(cell for cell, _ in rule_cells) + " |")
    return out


def process(text):
    """Align every table in `text`."""
    out = []
    for kind, payload in iter_blocks(split_lines(text)):
        out.extend(format_table(payload) if kind == TABLE else [payload])
    return "\n".join(out) + "\n"


def check(path, text):
    """Report tables whose rows do not all share the same display width."""
    ok = True
    line_number = 0

    for kind, payload in iter_blocks(split_lines(text)):
        if kind != TABLE:
            line_number += 1
            continue

        widths = sorted({rendered_width(line) for line in payload})
        if len(widths) > 1:
            print("%s:%d: table rows have differing widths: %s"
                  % (path, line_number + 1, ", ".join(str(w) for w in widths)))
            ok = False
        line_number += len(payload)

    return ok


def read(path):
    """Read a file as text, keeping the line endings in the string."""
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path, text, original):
    """Write `text` back using the line ending style found in `original`."""
    newline = "\r\n" if "\r\n" in original else "\n"
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text.replace("\n", newline))


def stamped_path(path, suffix, directory):
    """Build the output path for `path`, e.g. report_2026-1002-1058.md."""
    stem, extension = os.path.splitext(os.path.basename(path))
    directory = directory or os.path.dirname(os.path.abspath(path))
    return os.path.join(directory, stem + suffix + (extension or ".md"))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", metavar="FILE", help="markdown files to process")
    parser.add_argument("--check", action="store_true",
                        help="only report misaligned tables, do not write anything")
    parser.add_argument("--in-place", action="store_true",
                        help="overwrite the input files instead of writing stamped copies")
    parser.add_argument("--suffix", metavar="TEXT", default=DEFAULT_SUFFIX,
                        help="suffix appended to the output name (default: %(default)s)")
    parser.add_argument("--output", metavar="DIR",
                        help="directory for the output files (default: next to the input)")
    args = parser.parse_args()

    failed = False
    for path in args.files:
        try:
            original = read(path)
        except (OSError, UnicodeDecodeError) as error:
            # Keep the message readable, the batch file shows it to the user.
            detail = getattr(error, "strerror", None) or error
            print("ERROR: cannot read %s (%s)" % (path, detail), file=sys.stderr)
            failed = True
            continue

        if args.check:
            failed = not check(path, original) or failed
            continue

        result = process(original)
        target = path if args.in_place else stamped_path(path, args.suffix, args.output)
        try:
            write(target, result, original)
        except OSError as error:
            print("ERROR: cannot write %s (%s)" % (target, error.strerror or error), file=sys.stderr)
            failed = True
            continue
        print("%s -> %s" % (path, target))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
