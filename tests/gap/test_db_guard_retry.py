import sqlite3
import unittest
from unittest.mock import MagicMock, call, patch

from llmc_mcp.db_guard import DbTransactionManager
from llmc_mcp.maasl import DbBusyError


class TestDbGuardRetry(unittest.TestCase):
    def setUp(self):
        self.mock_conn = MagicMock(spec=sqlite3.Connection)
        # Mock in_transaction property to be False initially to avoid rollback calls before BEGIN
        self.mock_conn.in_transaction = False

    @patch("time.sleep")
    @patch("llmc_mcp.db_guard.get_maasl")
    def test_retry_logic_scenario_a_success(self, mock_get_maasl, mock_sleep):
        """
        Scenario A: Success after retries

        1. Mock db_conn.execute.
        2. Side effect: Raise sqlite3.OperationalError("database is locked") for the first 2 calls, then succeed.
        3. Expectation: write_transaction succeeds, no exception raised.
        """
        # Mock MAASL stomp_guard
        mock_maasl_instance = MagicMock()
        mock_get_maasl.return_value = mock_maasl_instance
        # Make stomp_guard a proper context manager
        mock_maasl_instance.stomp_guard.return_value.__enter__.return_value = None

        # Setup db_conn.execute side effects
        # 1. Fail (BEGIN IMMEDIATE)
        # 2. Fail (BEGIN IMMEDIATE)
        # 3. Success (BEGIN IMMEDIATE)
        # 4. Success (User query)
        self.mock_conn.execute.side_effect = [
            sqlite3.OperationalError("database is locked"),
            sqlite3.OperationalError("database is locked"),
            MagicMock(),  # Success BEGIN
            MagicMock(),  # Success User Query
        ]

        manager = DbTransactionManager(self.mock_conn, max_retries=3, retry_delay_ms=10)

        with manager.write_transaction() as conn:
            conn.execute("INSERT INTO test VALUES (1)")

        # Verify calls
        # We expect 3 calls to BEGIN IMMEDIATE (2 fails + 1 success)
        # And 1 call to INSERT
        self.assertEqual(self.mock_conn.execute.call_count, 4)
        expected_calls = [
            call("BEGIN IMMEDIATE"),
            call("BEGIN IMMEDIATE"),
            call("BEGIN IMMEDIATE"),
            call("INSERT INTO test VALUES (1)"),
        ]
        self.mock_conn.execute.assert_has_calls(expected_calls)

        # Verify commit was called
        self.mock_conn.commit.assert_called_once()

        # Verify sleep was called twice
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep")
    @patch("llmc_mcp.db_guard.get_maasl")
    def test_retry_logic_scenario_b_exhaust(self, mock_get_maasl, mock_sleep):
        """
        Scenario B: Exhaust retries

        1. Mock db_conn.execute.
        2. Side effect: Always raise sqlite3.OperationalError("database is locked").
        3. Expectation: write_transaction raises DbBusyError.
        """
        mock_maasl_instance = MagicMock()
        mock_get_maasl.return_value = mock_maasl_instance
        mock_maasl_instance.stomp_guard.return_value.__enter__.return_value = None

        # Always fail with locked
        self.mock_conn.execute.side_effect = sqlite3.OperationalError(
            "database is locked"
        )

        manager = DbTransactionManager(self.mock_conn, max_retries=3)

        with self.assertRaises(DbBusyError):
            with manager.write_transaction():
                pass

        # calls: initial + 3 retries = 4 calls to BEGIN IMMEDIATE
        self.assertEqual(self.mock_conn.execute.call_count, 4)
        self.mock_conn.execute.assert_called_with("BEGIN IMMEDIATE")

        # sleep called 3 times
        self.assertEqual(mock_sleep.call_count, 3)

    @patch("time.sleep")
    @patch("llmc_mcp.db_guard.get_maasl")
    def test_retry_logic_scenario_c_other_error(self, mock_get_maasl, mock_sleep):
        """
        Scenario C: Other errors propagate

        1. Mock db_conn.execute.
        2. Side effect: Raise sqlite3.OperationalError("syntax error").
        3. Expectation: write_transaction raises sqlite3.OperationalError immediately (no retry).
        """
        mock_maasl_instance = MagicMock()
        mock_get_maasl.return_value = mock_maasl_instance
        mock_maasl_instance.stomp_guard.return_value.__enter__.return_value = None

        self.mock_conn.execute.side_effect = sqlite3.OperationalError("syntax error")

        manager = DbTransactionManager(self.mock_conn)

        with self.assertRaises(sqlite3.OperationalError) as cm:
            with manager.write_transaction():
                pass

        self.assertIn("syntax error", str(cm.exception))

        # Only 1 call, no retries
        self.assertEqual(self.mock_conn.execute.call_count, 1)
        mock_sleep.assert_not_called()
