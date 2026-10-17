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

- `master` is the stable version. Releases are tagged from it (`v*`).
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
