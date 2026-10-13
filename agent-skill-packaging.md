# Packaging a Script as a Reusable Tool

How to turn a one-off script into a self-contained folder that both an agent
can invoke on its own and a non-technical user can operate by dragging a file
onto a `.cmd`. The reference implementation is `md-table-aligner/`.

## 1. Qualify the work first

Package something as a tool only when all three hold:

1. It is **repeated** work with a deterministic answer, not a one-off edit.
2. It is **safe to re-run**, so an agent can call it without previewing.
3. Its **correctness is checkable**, so the agent can confirm the result.

If any fails, fix the script first. A tool that an agent cannot verify is
worse than no tool, because it gets trusted.

## 2. Layout

Full form, for anything with non-trivial logic:

```
<tool-name>/
├── README.md                    # the interface doc, always present (section 4)
├── drop-<thing>-here.cmd        # entry point: humans drag files onto this
├── SKILL.md                     # only when the tool needs AI guidance (section 3)
└── internal/                    # implementation and developer notes
    ├── <tool>.py
    ├── test_<tool>.py
    └── NOTES.md
```

Trivial form, when the entry files **are** the whole implementation — one
command per OS, no branches worth hiding, nothing worth unit-testing (think:
"kill the process named X"): no implementation and no tests. The README is
still required — one screen of interface; the only extra file may be
`internal/usage.md` (section 5), which also carries the exit-code
meanings.

```
<tool-name>/
├── README.md                # still required — the interface doc
├── <tool-name>.bat           # no-argument entry (.cmd if it takes arguments)
├── <tool-name>.sh            # same command for Linux/macOS
└── internal/usage.md         # only when an entry prints usage (section 5)
```

In-tree examples: `stop-process/` (the whole logic is `taskkill`/`pkill` on a
name the user passes; its `internal/` holds only `usage.md`) and
`close-qgc/` (one delegation line to it, no `internal/` because it prints
nothing) — README plus the entry files is the entire tool.

Rules that are not negotiable:

- **`internal/`, never `scripts/`** — when the package has one. The split is
  not "code vs nothing", it is "what a user or an agent may rely on" vs
  "what may change". Anything under `internal/` is allowed to break without
  notice. Never create `internal/` just to hold one line of shell — an empty
  abstraction layer is worse than none.
- The entry point sits at the **package root**, so it is the first thing
  a user sees in Explorer.
- Prefer the standard library; use a mainstream library when it is the
  better tool. List any dependency in the README, so an agent in a bare
  environment knows what must be installed first.

## 3. SKILL.md, only when the tool needs AI guidance

Not a default. Add one only when the tool genuinely needs AI usage
guidance, a judgment flow, or task coordination with other tools — a
deterministic tool whose interface is clear from the README does not get
one, because a boilerplate SKILL costs context and adds nothing. None of
the in-tree tools currently have one. When present, it sits beside the
README (which stays the full interface doc) and is the only file loaded
on trigger: budget under 60 lines.

### Frontmatter

```yaml
---
name: <kebab-case-name>
description: <what it does>. Use when <trigger 1>, when asked to <verb set>,
  before <milestone>, or when <user action>. <Critical default behaviour>.
---
```

The `description` is the **only** thing an agent sees before deciding to load
it. Two rules:

- Write **when to use it**, not what it is. "Lines up markdown table columns.
  Use when markdown tables look ragged in plain text, when asked to
  align/format/fix markdown tables, or before committing documentation" works.
  "A tool for formatting markdown" does not, because it matches nothing.
- State the **default side effect** in the description. "Writes a timestamped
  copy next to the source and leaves the original untouched unless
  `--in-place` is given" stops the agent from guessing wrong.

### Body

Sections, in this order:

1. `## Commands` — one fenced block, one line per invocation, comment on the
   right of each command. This is what the agent copies.
2. `## Options` — only when there are flags to document: a flag table, one
   row per flag including the default. Skills without flags omit the section.
3. Exit codes — one sentence, so the agent can branch on failure.
4. `## Guarantees` — the behaviours the agent can rely on and does not need to
   re-verify.

Close with a single conditional pointer **when the tool has
`internal/NOTES.md`**:

> Read `internal/NOTES.md` only if the output looks wrong or you need to change
> the script.

A tool without `internal/NOTES.md` ends after Guarantees. Never end with
a bare "see also" list. That is how an agent ends up reading
four files to run one command.

## 4. README.md, the interface doc

Always present at the tool root — the single document both humans and
agents read to call the tool. It must **not** contain a link to
`SKILL.md`: agents discover skills through the registry frontmatter, so a
pointer from README only serves to make an agent that stumbled onto README
open two more files for nothing. Pointers to `internal/` appear only in
the two canonical forms — an `internal/...` path inside a command line,
and the single conditional `internal/NOTES.md` pointer that closes the
file (section 3's wording). Never end with a bare "see also" list.

Content order:

1. One sentence on what it does, in the user's terms, plus when to use it.
2. Drag and drop, with the resulting filename shown concretely (only when
   the tool has a drag entry).
3. Command lines, most common first.
4. Arguments/flags table, only when there are any.
5. Exit codes — one sentence, so the caller can branch on failure.
6. Requirements, and the exact error text if they are missing.
7. Guarantees — what the tool does and does **not** touch. This is the
   section that prevents support questions about code samples or pipes
   in prose.

A wrapper tool — one that only fixes an argument and delegates to a
sibling tool — keeps the same sections but does not restate the
underlying tool's behaviour: the intro names the sibling's README,
item 7 is replaced by that one pointer, and item 5 may open with
"same as `<tool>` —" followed by the mapping. Duplicating the
guarantees only creates two copies to keep in sync.

## 5. Entry filenames and the drag entry point

Naming rules, for every entry file:

- **Lowercase ASCII**, like every other name in the package (folder, tool
  name, scripts). The entry basename then matches the tool name 1:1
  (`close-qgc/` → `close-qgc.bat`), tab-completion and case-sensitive
  filesystems stay happy, and modern CLI tools are lowercase anyway
  (`taskkill`, `winget`, `npm.cmd`). The words carry the shout, not the
  case.
- **`-here` suffix means "drop something onto this file"** and belongs only
  to entries that actually receive dropped files or folders. A plain command
  entry takes no payload and is named after its tool alone
  (`close-qgc.bat`, not `close-qgc-here.bat`).
- **`.bat` = takes no arguments; `.cmd` = takes arguments.** The extension
  tells you the contract before you open the file: `close-qgc.bat` is a pure
  action (double-click or run as-is, no `--help`, nothing to parse),
  `stop-process.cmd <name>` consumes input.
- **Usage text lives in `internal/usage.md`**, printed by the entry
  (`type "%~dp0internal\usage.md"` / `cat "$(dirname "$0")/internal/usage.md"`).
  Never inline `echo` or heredoc blocks in the entry — they age badly and
  bury the control flow. Exit-code meanings go in that same `usage.md`,
  never as a comment block in the script header.

```
drop-md-file-here.cmd        good (drag entry, takes file arguments)
drop-qgc-folder-here.cmd     good (drag entry, takes a folder argument)
close-qgc.bat                good (command entry, takes no arguments)
stop-process.cmd             good (command entry, takes arguments)
close-qgc-here.cmd           bad, nothing is dropped onto it
close-qgc.cmd                bad, no arguments (that is what .bat is for)
DROP-MD-FILE-HERE.cmd        bad, uppercase
align_tables.cmd             bad, says nothing about dropping
```

The rest of this section applies to drag entries specifically.

Implementation checklist:

| Requirement                                                                                                                               | Reason                                                                                            |
| ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Call `python` directly — no interpreter-locating helper                                                                                   | A missing Python prints its own error; a `py -3` fallback hides which interpreter ran             |
| Quote every path, use `"%~f1"`                                                                                                            | Spaces and non-ASCII names                                                                        |
| Do not enable delayed expansion                                                                                                           | `!` in a filename would be consumed                                                               |
| Loop with `shift` over `"%~1"`                                                                                                            | Windows allows dropping several files                                                             |
| Escape `<` and `>` as `^<` and `^>` inside `echo`                                                                                         | Unescaped they become redirection                                                                 |
| Print a usage screen when run with no arguments                                                                                           | It is also double-clickable                                                                       |
| No `--help` flag: no arguments already prints usage (exit 2)                                                                              | One rule, one usage path — no second help screen to maintain                                      |
| Never inspect argument shape — `-` prefixes are valid payload names; pass values through as-is                                            | A folder literally named `-` must not be rejected as a flag                                       |
| `pause` only when the entry printed text a human must read (usage, error, result report); a silent side-effect entry exits with no prompt | A required keypress is a human-in-the-loop step; automation stalls at `Press any key to continue` |
| Exit non-zero on failure                                                                                                                  | Lets CI and agents detect it                                                                      |
| End `.cmd` files with CRLF line endings                                                                                                   | cmd.exe quirks with LF-only batch                                                                 |

> Wrappers that wait on a long-running child (GUI app, dev server) should
> launch it with `start "Title" python "script.py" %*` in its **own console
> window**. A cmd.exe that is busy running a batch file answers Ctrl+C with
> `Terminate batch job (Y/N)?`; a window where only the child runs cannot
> produce that prompt at all. The wrapper window then exits immediately, and
> the child's window owns any "press Enter" wait (e.g. via a `--pause`
> flag). Reference: `qgc4-launch-with-logs/`.

## 6. Implementation rules

These are what make the tool safe for an unattended agent:

- **Never modify the input** unless an explicit `--in-place` flag is passed.
  Write a new file with a distinguishable name instead.
- **Idempotent.** Running twice yields byte identical output.
- **Preserve line endings.** Read with `newline=""`, detect CRLF, write back
  the same style.
- **One timestamp per invocation**, not per file, so a multi-file run produces
  a consistent set of names.
- **Never write a timestamp into a `--check` run**, and make `--check` the safe
  default for agents that only want to know whether work is needed.
- **Report failures as one line on stderr**, never a traceback. The batch file
  prints that text to a user who did not ask for a stack trace.

## 7. Tests

Only when the package has real logic. Put tests in `internal/`, standard
library `unittest` by default so they run in a bare environment; if the
package uses a mainstream test runner instead, state the command in the
README. A trivial self-contained package (section 2) needs no tests — verify
it by running the entry once (section 9).
Two files should both work:

```bash
python3 internal/test_<tool>.py                          # direct
python3 -m unittest discover <package>/internal -v      # discovery
```

Add one "invariants" test case that loops over every sample and asserts the
section 6 properties, so each new sample is covered automatically:

```python
def test_idempotent_is_required(self):
    for sample in self.SAMPLES:
        once = fmt.process(sample)
        self.assertEqual(fmt.process(once), once)
```

When adding a sample to `SAMPLES`, write the **observed** output as the
expected string. Guessing the padding by eye wastes more time than reading the
actual result.

## 8. internal/NOTES.md

Only for packages that have an `internal/`. For developers, never loaded by
an agent. Keep:

- **Layout** — one line per file saying what it owns.
- **How to run the tests.**
- **The detection rules** — what the tool treats as input and what it skips,
  with the reason. This is the section that stops a future reader from
  "fixing" deliberate behaviour.
- **The algorithm**, step by step, at the level of "what order and why".
- **Known limitations**, stated plainly. A limitation nobody wrote down becomes
  a bug report.
- **Invariants to preserve when editing.**

## 9. Verification checklist

```bash
# From the repo root: every package test, md check, README audit,
# .cmd CRLF check, and a usage smoke of the .sh entries that print usage
python3 test_repo.py

# Entry points on Windows need one manual run (cmd.exe cannot execute here)
cmd /c "<package>\<entry>.bat"                    # no-argument entries (.bat): just run
cmd /c "<package>\<entry>.cmd" <real input>
git status --short <sample>                       # expect unmodified after drag
```

## 10. Anti-patterns

Each of these shipped as a real bug while building the reference package.

| Anti-pattern                                                     | Failure                                                               |
| ---------------------------------------------------------------- | --------------------------------------------------------------------- |
| Splitting a markdown row on `\|` before stripping the outer pipes | Two empty columns per row, and every rerun adds more                  |
| `echo <name>_...` in a `.cmd`                                    | `cmd` reads it as input redirection and prints a file-not-found error |
| Letting a `FileNotFoundError` propagate                          | The user sees a Python traceback from a drag-and-drop                 |
| Column widths that ignore `:---:` colons                         | Separator row is one or two columns wider than the data rows          |
| Unescaping `\|` on read and never re-escaping on write            | Second run splits the cell in two                                     |
| Forcing a separator row onto any `\| ... \|` line                  | A pipe in ordinary prose silently becomes a table header              |
| Counting CJK characters as one column                            | Every Chinese table comes out ragged                                  |
| Linking README to SKILL.md                                       | An agent that reads README opens three files to run one command       |
| Creating `internal/` for trivial logic                           | An empty abstraction layer agents are told to read but learn nothing  |
| Unconditional `pause` after a silent side-effect command         | Every automated run stops at `Press any key to continue`              |
| Guessing expected test output instead of running the tool        | Wasted time and tests that assert the wrong thing                     |
