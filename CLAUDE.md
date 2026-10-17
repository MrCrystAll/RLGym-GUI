# RLGym GUI

Three parts: `rlgym-app/` (Angular UI), `rlgym-server/` (FastAPI backend + Python worker) and
`electron/` (desktop shell that spawns the backend).

## Workflow

### Every change has a Jira ticket

All work is tracked in the **RLGYM** project on https://mathsuch63.atlassian.net. No change goes in
without a ticket. Ticket summaries start with the area they touch: `API:`, `GUI:`, `API - GUI:`,
`Worker:`, `CI:`, `Docs:`...

Before creating any Jira item (epic, feature, task, bug...), show a draft of it (type, parent,
summary, description) and wait for approval, unless explicitly asked to create tickets in bulk.

### Branches

- `master` is the stable version. Every release is a `v*` tag on it (see [Releases](#releases)).
- `dev` is the nightly version. Ticket branches start from it and merge back into it.

Ticket branches follow git flow and are named `<type>/RLGYM-<n>_<short-description>`:

| Type       | For                                  | Branches from |
| ---------- | ------------------------------------ | ------------- |
| `feature`  | new functionality, docs, tooling     | `dev`         |
| `bugfix`   | a bug found on `dev`                 | `dev`         |
| `hotfix`   | an urgent fix to the stable version  | `master`      |
| `release`  | preparing a version for `master`     | `dev`         |

Example: `feature/RLGYM-25_document-dev-workflow`.

### Commits and pull requests

- Every commit message contains the ticket key, e.g. `RLGYM-25 Add PR template`.
- PR title: `<type>: RLGYM-<n> - <short description>`, e.g. `feature: RLGYM-25 - Document the dev workflow`.
- The PR body says what changed and why, and links the ticket. Use the template in
  `.github/pull_request_template.md`.
- Pull requests target `dev`, except hotfixes and releases, which target `master`.

Jira is connected to GitHub, so a ticket key in the branch name, commits and PR is enough for them
to show up in the ticket's Development panel.

### Changelog

Every bug fix, feature or change the end user can see gets an entry in `rlgym-app/CHANGELOG.md`,
under `## Unreleased`, in the matching [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
section (`Added`, `Changed`, `Fixed`, `Removed`...). Internal-only changes (CI, refactors, docs for
developers) don't need one. The release workflow refuses to publish a version without a changelog
section.

### Releases

A release is a ticket like any other (`Release: x.y.z`). Versions follow semver; the version lives
in `electron/package.json` (what the app and the auto-updater see) and `rlgym-app/package.json`,
which must match.

1. Branch `release/RLGYM-<n>_<x.y.z>` from `dev`.
2. Run `node scripts/release.mjs <x.y.z>`. It bumps both `package.json` files and their lockfiles,
   and turns `## Unreleased` into `## [x.y.z] - YYYY-MM-DD` under a new, empty `## Unreleased`.
   It refuses an empty Unreleased section or a version that isn't higher. Review the diff, commit
   (`RLGYM-<n> Release x.y.z`) and push.
3. Open a PR to `master`: `release: RLGYM-<n> - x.y.z`, label `release`.
4. Merging it runs `.github/workflows/release.yml`: it builds the app, tags `vx.y.z` on the merge
   commit, publishes the GitHub Release (installers + `latest.yml` for the auto-updater) with the
   changelog section as notes, and opens a `master` → `dev` back-merge PR.
5. Merge the back-merge PR with a merge commit (not a squash), so `master` stays an ancestor of
   `dev`.

A hotfix is the same, except it branches from `master` (`hotfix/RLGYM-<n>_<description>`), bumps
the patch version and has a `Fixed` changelog entry.

Pushing a `v*` tag by hand still triggers a release, as a fallback; the tag must match the
`package.json` versions. The back-merge PR needs "Allow GitHub Actions to create and approve pull
requests" in the repository settings; without it, open that PR by hand.
