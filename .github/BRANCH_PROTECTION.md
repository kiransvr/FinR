# Branch Protection Policy

## Target Branch

- `main`

## Required Settings

- Require a pull request before merging.
- Require at least 1 approving review.
- Dismiss stale approvals when new commits are pushed.
- Require conversation resolution before merge.
- Require status checks to pass before merging.

## Required Status Checks

- `Backend CI / backend-build-test-lint`
- `Dependency Scan / dependency-check`

## Merge Policy

- Do not allow direct pushes to `main` except for repository administrators in emergency scenarios.
- Squash merge or rebase merge is preferred for clean story-by-story history.
- Any failed required check blocks merge until fixed.

## Security Threshold

- Dependency scan blocks merge when CVSS is 7.0 or higher.

## Operational Notes

- Update required status checks if workflow job names change.
- Review this policy whenever branching or release strategy changes.