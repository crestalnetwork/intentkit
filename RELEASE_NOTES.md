# Release Notes

## 0.10.3

### CI/CD

- **GitHub Workflows**:
    - Removed `push` trigger from `build.yml` (now only triggers on release).
    - Replaced Slack notifications with Telegram notifications in `build.yml`.
    - Removed unnecessary checkout step and pre-build notification in Docker job.
    - Added unit test step to `lint.yml` (`pytest -m "not bdd"`).
