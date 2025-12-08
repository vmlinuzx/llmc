# SDD: DbTransactionManager Retry Logic Coverage

## 1. Gap Description
The current test `tests/test_maasl_db_guard.py::test_sqlite_busy_retry` only asserts configuration values (`max_retries`, `retry_delay_ms`). It does **not** verify that the retry logic actually executes when `sqlite3.OperationalError: database is locked` occurs.

We need to verify:
1.  The `write_transaction` method retries when it encounters a locked database.
2.  It respects the `max_retries` limit.
3.  It raises `DbBusyError` if retries are exhausted.
4.  It successfully proceeds if the lock clears within the retry limit.

## 2. Target Location
`tests/gap/test_db_guard_retry.py`

## 3. Test Strategy
We will use `unittest.mock` to mock the `sqlite3.Connection` object and its `execute` method.

**Scenario A: Success after retries**
1.  Mock `db_conn.execute`.
2.  Side effect: Raise `sqlite3.OperationalError("database is locked")` for the first 2 calls, then succeed.
3.  Expectation: `write_transaction` succeeds, no exception raised.

**Scenario B: Exhaust retries**
1.  Mock `db_conn.execute`.
2.  Side effect: Always raise `sqlite3.OperationalError("database is locked")`.
3.  Expectation: `write_transaction` raises `DbBusyError`.

**Scenario C: Other errors propagate**
1.  Mock `db_conn.execute`.
2.  Side effect: Raise `sqlite3.OperationalError("syntax error")`.
3.  Expectation: `write_transaction` raises `sqlite3.OperationalError` immediately (no retry).

## 4. Implementation Details
- Use `unittest.mock.MagicMock` for the connection.
- Use `unittest.mock.patch` if necessary, or just pass the mock to `DbTransactionManager`.
- Ensure `time.sleep` is mocked to speed up tests.
- Verify `conn.execute` call count matches expected retries.
