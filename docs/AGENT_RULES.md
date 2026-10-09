1. Start every session by reading PROGRESS.md and this file. Read other files only when today's prompt needs them. Prefer `grep -n "def "` or `head` over opening whole files.
2. If PROGRESS.md shows the previous day's checks failing, fix that first with minimal changes, then continue.
3. Do only today's objective. Do not refactor earlier modules unless a test fails or today's work requires it.
4. Make small, targeted edits. Never reprint unchanged code in replies.
5. Never re-download data when the cache exists. Never generate synthetic data except inside unit tests.
6. Never touch the test period before the Day 10 freeze. The code enforces this via unlock_test.
7. Add no new dependency without a one-line justification in the PROGRESS.md decisions log.
8. Never write a performance number that is not read from a file in reports/results/.
9. Keep terminal output short: never print a DataFrame longer than 20 rows, and show full tracebacks only when debugging.
10. Before finishing, run that day's tests and then the full `pytest -q`, add at most 30 lines to PROGRESS.md (implemented, tested, remaining, next commands, decisions), and commit as "dayNN: <summary>".
11. Keep the final reply under 200 words.
