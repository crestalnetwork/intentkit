# Operations Guide

This guide provides detailed information for Git operations and release management in IntentKit.

## Git Commit

### Pre-commit Steps

1. Run `ruff format && ruff check --fix` before commit.

### Commit Message Format

When you generate git commit message, always start with one of `feat/fix/chore/docs/test/refactor/improve`. 

**Format**: `<type>: <subject>`

- Subject should start with lowercase
- Only one-line needed, do not generate commit message body

**Examples**:
- `feat: add new twitter skill`
- `fix: resolve circular dependency in models`
- `chore: update dependencies`

## Github Release

### Version Number Rules

Follow Semantic Versioning:
- **Pre-release**: `vA.B.C-devD`
- **Release**: `vA.B.C`

#### Version Calculation

- **Release**: +1 to patch version `C`
- **Pre-release**: +1 to `D` of `-devD`, but if `vA.B.C` already released, next pre-release should restart from next patch version `vA.B.(C+1)-dev1`

**Examples**:
- Next pre-release of `v0.1.2-dev3` → `v0.1.2-dev4`
- If `v0.1.2` production release already published, next pre-release → `v0.1.3-dev1`

### Release Steps

1. Make a `git pull --rebase` first. If the local branch is main,  `git push` it.

2. Find the last version number in release or pre-release using:
   ```bash
   git tag --sort=-version:refname | head -15
   ```

3. Diff `origin/main` with it, summarize release notes to business language, not a technical one. List new features. For bug fixes and improvements, provide vague descriptions, such as "fixed bugs in the xxx module". Then save it to `latest_changelog.md` for later use. Add a diff link to release note too, the from and to should be the version number.

4. If the release is **not pre-release**, also insert the release note to the beginning of `CHANGELOG.md` (This file contains all history release notes, don't use it in gh command). Commit and push these doc changes.

5. Construct `gh release create` command, use `latest_changelog.md` as notes file in gh command.

6. Use `gh` to publish release only, don't create branch, tag, or pull request.
