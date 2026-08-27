import os
import ssl
import sys
import unittest
from unittest.mock import MagicMock, patch

# main.py reads these at import time and exits when one is missing,
# so they have to be set before the import below
os.environ.setdefault("EMAIL_SENDER_ADDRESS", "sender@example.com")
os.environ.setdefault("EMAIL_SENDER_APP_PASSWORD", "dummy-app-password")
os.environ.setdefault("EMAIL_RECIPIENT", "recipient@example.com")

# src/ is not a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main


class TestGetRandomMessage(unittest.TestCase):
    def test_returns_a_message_from_the_list(self):
        self.assertIn(main.getRandomMessage(), main.messages)

    def test_uses_the_index_random_returns(self):
        with patch("random.randint", return_value=3) as mock_randint:
            self.assertEqual(main.getRandomMessage(), main.messages[3])
        mock_randint.assert_called_once_with(0, len(main.messages) - 1)


class TestSendEmail(unittest.TestCase):
    def test_builds_the_message_with_from_to_and_subject_headers(self):
        server = MagicMock()
        with patch("builtins.print"):
            main.sendEmail(
                server, "a@example.com", "b@example.com", "Subject line", "Body line"
            )
        server.sendmail.assert_called_once_with(
            "a@example.com",
            "b@example.com",
            "From: a@example.com\nTo: b@example.com\nSubject: Subject line\n\nBody line",
        )

    def test_reports_the_recipient(self):
        server = MagicMock()
        with patch("builtins.print") as mock_print:
            main.sendEmail(server, "a@example.com", "b@example.com", "s", "b")
        mock_print.assert_called_with("Email sent to b@example.com!")


class TestUseSSL(unittest.TestCase):
    @patch("smtplib.SMTP_SSL")
    def test_connects_to_gmail_on_465_and_sends(self, mock_smtp_ssl):
        server = mock_smtp_ssl.return_value.__enter__.return_value

        with patch("builtins.print"):
            main.useSSL()

        self.assertEqual(mock_smtp_ssl.call_args[0][:2], ("smtp.gmail.com", 465))
        self.assertIsInstance(mock_smtp_ssl.call_args[1]["context"], ssl.SSLContext)
        server.login.assert_called_once_with(
            main.EMAIL_SENDER_ADDRESS, main.EMAIL_SENDER_APP_PASSWORD
        )
        sender, receiver, message = server.sendmail.call_args[0]
        self.assertEqual(sender, main.EMAIL_SENDER_ADDRESS)
        self.assertEqual(receiver, main.EMAIL_RECIPIENT)
        self.assertIn("Subject: Test email from Python", message)
        self.assertTrue(any(m in message for m in main.messages))


class TestUseTLS(unittest.TestCase):
    @patch("smtplib.SMTP")
    def test_connects_to_gmail_on_587_and_upgrades_before_login(self, mock_smtp):
        server = mock_smtp.return_value

        with patch("builtins.print"):
            main.useTLS()

        self.assertEqual(mock_smtp.call_args[0], ("smtp.gmail.com", 587))
        self.assertEqual(
            [name for name, _, _ in server.method_calls],
            ["ehlo", "starttls", "ehlo", "login", "sendmail", "quit"],
        )
        self.assertIsInstance(server.starttls.call_args[1]["context"], ssl.SSLContext)
        server.login.assert_called_once_with(
            main.EMAIL_SENDER_ADDRESS, main.EMAIL_SENDER_APP_PASSWORD
        )
        server.quit.assert_called_once_with()

    @patch("smtplib.SMTP")
    def test_swallows_a_send_failure_and_still_quits(self, mock_smtp):
        # characterizes the behavior reported in issue #5: the exception is
        # printed and useTLS returns normally, so the caller sees success
        server = mock_smtp.return_value
        server.sendmail.side_effect = Exception("550 rejected")

        with patch("builtins.print") as mock_print:
            self.assertIsNone(main.useTLS())

        server.quit.assert_called_once_with()
        self.assertIn("550 rejected", [str(c[0][0]) for c in mock_print.call_args_list])

    @patch("smtplib.SMTP", side_effect=OSError("connection refused"))
    def test_raises_unbound_local_error_when_the_connection_fails(self, mock_smtp):
        # characterizes the bug reported in issue #4: the finally block
        # references server before it was assigned, masking the real error
        with patch("builtins.print"):
            with self.assertRaises(UnboundLocalError):
                main.useTLS()


class TestRun(unittest.TestCase):
    def test_s_selects_ssl(self):
        with patch("builtins.input", return_value="s"), patch.object(
            main, "useSSL"
        ) as mock_ssl, patch.object(main, "useTLS") as mock_tls:
            main.run()
        mock_ssl.assert_called_once_with()
        mock_tls.assert_not_called()

    def test_t_selects_tls(self):
        with patch("builtins.input", return_value="t"), patch.object(
            main, "useSSL"
        ) as mock_ssl, patch.object(main, "useTLS") as mock_tls:
            main.run()
        mock_tls.assert_called_once_with()
        mock_ssl.assert_not_called()

    def test_anything_else_connects_to_nothing(self):
        with patch("builtins.input", return_value="x"), patch.object(
            main, "useSSL"
        ) as mock_ssl, patch.object(main, "useTLS") as mock_tls, patch(
            "builtins.print"
        ) as mock_print:
            main.run()
        mock_ssl.assert_not_called()
        mock_tls.assert_not_called()
        mock_print.assert_called_once_with("Invalid input! Please type 's' or 't'.")


if __name__ == "__main__":
    unittest.main()
