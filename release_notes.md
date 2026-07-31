## Bug Fixes

- Editing an agent that has a custom URL name now saves correctly. Previously, if you opened an agent's edit page, made a change, and reloaded the page before saving, the save could fail with an "agent not found" error.

## Improvements

- Codebase-wide quality pass: the project's automated code checks were expanded from a small hand-picked set to the linter's full recommended set, and roughly 1,600 findings were resolved across the codebase. Most were stylistic, but the sweep also corrected a few real issues, including timestamps recorded without a timezone in the autonomous task scheduler and the DeFi Llama market-data client, and error logs that repeated the same error text twice. Failure-case tests were tightened to verify the specific error they expect instead of accepting any failure.
- Removed an unused third-party dependency, slightly reducing install size.
