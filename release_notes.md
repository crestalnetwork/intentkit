# Release v2.7.1

## Improvements

- Database schema upgrades now run automatically when services start — deploying a new version no longer requires any manual migration step. Existing databases are adopted in place on their first start after this release, several services starting at the same time coordinate safely, and a service will refuse to start on a database it could not upgrade rather than run with a mismatched schema.
