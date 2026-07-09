# Release v2.14.1

## Improvements

- Fixed a database upgrade from the previous release that could fail to start the background services — including scheduled autonomous tasks — on deployments whose database was missing certain optional tables. The schema upgrade now applies safely regardless of which of those tables a database already has.
