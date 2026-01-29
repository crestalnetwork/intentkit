## New Features
- Implement soft-off credit charging policy: Allow expenses processing even when payment is disabled (recording costs as 0 or discounted).
- Adjust `expense_summarize` and `expense_message` to correctly handle `created_at` timestamp for Credit Events.

## Improvements
- Enhanced test coverage for credit calculations.

[Full Changelog](https://github.com/crestalnetwork/intentkit/compare/v0.9.14...v0.9.15)