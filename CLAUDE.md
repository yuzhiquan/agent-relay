# The Loop Protocol

Every task runs as a loop, not a straight line.

## The Loop

1. Write the change.
2. Run the checks: tests + linter + type checker.
3. Failures? Read the error, find the cause, fix it, then go back to step 2.
4. Loop at most 5 times.

## Stop Conditions

- **All checks pass** → report "Done", with the passing output as proof.
- **5 iterations used up** → stop and report what's still failing.
- **The same error appears twice in a row** → stop immediately. You're guessing, not fixing.

## Forbidden

- Reporting "Done" without check output.
- Making tests pass by deleting assertions or weakening tests. Fix the code, not the scoreboard.
