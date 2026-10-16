# Security analysis records

## Public-source scanner output, 2026-10-16

CodeQL alert 1 (`py/clear-text-logging-sensitive-data`) follows the result of
`scripts/check_public.py:content_problems` to the CLI's output loop. The scanner
adds only a line number and a constant problem label to each finding. `audit`
adds the repository-relative filename; it never adds the regex match or file
contents. The CLI prints this location and label, not the matched credential.
This is a false positive for logging a matched credential value.

The end-to-end regression in `tests/test_fetch_upstream.py` stages an invented
credential and private-address pattern in a disposable Git repository, invokes
the actual scanner CLI, and checks both output streams: it must fail the scan,
report file/line/category, and omit both matched values. Existing tests also
verify the structured finding and staged-versus-worktree behavior. Repository
filenames can be printed and must themselves be suitable for public logs.

Two separate CodeQL quality findings about mixing `import unittest` with
`from unittest import mock` are fixed by using module-qualified imports. No
security query is disabled, no output value is masked after logging, and no
broad scanner suppression is added.
