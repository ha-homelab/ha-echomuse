# Shared CI and pull-request automation

The repository calls immutable revisions of
[venus-os-ci-toolkit](https://github.com/victron-venus/venus-os-ci-toolkit).
Update the full commit pins through a reviewed PR; do not replace them with
`main` or a floating tag.

## Required validation

`Quality gate` runs on pull requests, the merge queue, pushes to `main`, and
manual dispatch. Its single required check remains **CI gate**. That check
fails when any required job fails, is cancelled, is skipped, or is missing.

- Shared Python CI runs the offline regression suite with Python 3.11.
  Coverage is saved as a short-lived Actions artifact. The migration retains
  the previous test requirement without adding a new coverage percentage,
  formatter, or type-checking requirement.
- Shared security scanning runs CodeQL for Python and Actions, Trivy, and
  dependency review when applicable to a pull request.
- The repository-specific job compiles Python, parses the upstream lock, and
  runs `scripts/check_public.py` against tracked source. Device access,
  recordings, live HA credentials, and deployment are not needed for CI.

The ordinary validation jobs receive no `BOT_PAT`. The existing private-file
exclusions and public-source audit remain in force.

## Independent approval and opt-in merge

The shared approval workflow handles ready PRs from the toolkit's trusted
authors: `4alvit`, `californiantiramisu`, `dependabot[bot]`, and `renovate[bot]`.
For a human-authored PR, the organization `BOT_PAT` supplies the independent
`californiantiramisu` reviewer. The toolkit verifies the actual token owner,
PR author, current commit, target branch, and eligibility before reviewing.
It does not approve a PR as its own author.

Dependabot uses the explicitly scoped Actions token. The toolkit also supports
an independent `APPROVAL_PAT`, or its checked Actions-token fallback for an
eligible same-repository bot-authored PR. These are shared workflow policies;
this repository does not store or copy token values in source.

Approval and merging are separate. Add **automerge** to opt a PR into native
GitHub auto-merge. The pinned merge workflow verifies the protected CI gate
and requests a squash merge; GitHub still enforces current independent review,
strict branch freshness, resolved review threads, and successful checks.
Removing the label or making the PR a draft withdraws eligibility. Without
the label, approval leaves the PR open.

The metadata-only approval and merge callers use `pull_request` for
same-repository branches and `pull_request_target` for forks, following the
toolkit's existing trust in repository branch writers. Neither caller checks
out or executes PR source. CodeRabbit review requests and bounded autofix
requests also use pinned shared workflows; they do not replace the required
validation gate.

## Terraform-managed access

The [infrastructure repository](https://github.com/4alvit/terraform-github-ha-homelab)
manages native auto-merge, read-only default workflow permissions with explicit
approval support, the bot's repository **write** permission, and this
repository's membership in the existing organization `BOT_PAT` allowlist.
It does not replace the secret value or other repositories' grants.

Troubleshoot missing approvals by checking the metadata workflow logs, secret
allowlist membership, bot write access, and current-head review state. Do not
remove branch protection or lower the required review count to unblock a PR.
