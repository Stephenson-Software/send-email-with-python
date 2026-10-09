import os
import runpy
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

MAIN_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "main.py")
CREDENTIAL_VARIABLES = [
    "EMAIL_SENDER_ADDRESS",
    "EMAIL_SENDER_APP_PASSWORD",
    "EMAIL_RECIPIENT",
]


class TestCredentialGuards(unittest.TestCase):
    # the guards run at import time, so main.py is re-executed with one
    # variable removed or emptied rather than exercised through the imported module
    def run_main_without(self, variable, empty=False):
        with patch.dict(os.environ), patch(
            "builtins.input", side_effect=AssertionError("prompted")
        ) as mock_input, patch(
            "smtplib.SMTP", side_effect=AssertionError("connected")
        ) as mock_smtp, patch(
            "smtplib.SMTP_SSL", side_effect=AssertionError("connected")
        ) as mock_smtp_ssl, patch(
            "builtins.print"
        ) as mock_print:
            if empty:
                os.environ[variable] = ""
            else:
                del os.environ[variable]
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(MAIN_PATH, run_name="__main__")
        mock_input.assert_not_called()
        mock_smtp.assert_not_called()
        mock_smtp_ssl.assert_not_called()
        return caught.exception, mock_print

    def test_each_missing_variable_is_named_and_exits_before_prompting(self):
        for variable in CREDENTIAL_VARIABLES:
            with self.subTest(variable=variable):
                exception, mock_print = self.run_main_without(variable)
                self.assertEqual(exception.code, 1)
                mock_print.assert_called_once_with(
                    variable + " environment variable not set!"
                )

    def test_each_empty_variable_is_named_and_exits_before_prompting(self):
        for variable in CREDENTIAL_VARIABLES:
            with self.subTest(variable=variable):
                exception, mock_print = self.run_main_without(variable, empty=True)
                self.assertEqual(exception.code, 1)
                mock_print.assert_called_once_with(
                    variable + " environment variable not set!"
                )


class TestGetRandomMessage(unittest.TestCase):
    def test_returns_a_message_from_the_list(self):
        self.assertIn(main.getRandomMessage(), main.messages)

    def test_picks_from_the_whole_list_with_random_choice(self):
        with patch("random.choice", return_value="chosen") as mock_choice:
            self.assertEqual(main.getRandomMessage(), "chosen")
        mock_choice.assert_called_once_with(main.messages)


class TestSendEmail(unittest.TestCase):
    def test_builds_the_message_with_from_to_and_subject_headers(self):
        server = MagicMock()
        with patch("builtins.print"):
            main.sendEmail(
                server, "a@example.com", "b@example.com", "Subject line", "Body line"
            )
        (message,), _ = server.send_message.call_args
        self.assertEqual(message["From"], "a@example.com")
        self.assertEqual(message["To"], "b@example.com")
        self.assertEqual(message["Subject"], "Subject line")
        self.assertEqual(message.get_content(), "Body line\n")
        server.sendmail.assert_not_called()

    def test_rejects_a_newline_in_a_header_instead_of_injecting_it(self):
        server = MagicMock()
        with patch("builtins.print"):
            with self.assertRaises(ValueError):
                main.sendEmail(
                    server,
                    "a@example.com",
                    "b@example.com",
                    "Hello\nBcc: c@example.com",
                    "Body line",
                )
        server.send_message.assert_not_called()
        server.sendmail.assert_not_called()

    def test_reports_the_recipient(self):
        server = MagicMock()
        with patch("builtins.print") as mock_print:
            main.sendEmail(server, "a@example.com", "b@example.com", "s", "b")
        mock_print.assert_called_with("Email sent to b@example.com!")


class TestSendRandomMessage(unittest.TestCase):
    def test_sends_a_random_message_from_the_configured_sender_to_the_recipient(self):
        server = MagicMock()
        with patch.object(main, "getRandomMessage", return_value="picked body"), patch(
            "builtins.print"
        ):
            main.sendRandomMessage(server)
        (message,), _ = server.send_message.call_args
        self.assertEqual(message["From"], main.EMAIL_SENDER_ADDRESS)
        self.assertEqual(message["To"], main.EMAIL_RECIPIENT)
        self.assertEqual(message["Subject"], main.EMAIL_SUBJECT)
        self.assertEqual(message.get_content(), "picked body\n")


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
        (message,), _ = server.send_message.call_args
        self.assertEqual(message["From"], main.EMAIL_SENDER_ADDRESS)
        self.assertEqual(message["To"], main.EMAIL_RECIPIENT)
        self.assertEqual(message["Subject"], "Test email from Python")
        self.assertIn(message.get_content().rstrip("\n"), main.messages)


class TestUseTLS(unittest.TestCase):
    @patch("smtplib.SMTP")
    def test_connects_to_gmail_on_587_and_upgrades_before_login(self, mock_smtp):
        server = mock_smtp.return_value.__enter__.return_value

        with patch("builtins.print"):
            main.useTLS()

        self.assertEqual(mock_smtp.call_args[0], ("smtp.gmail.com", 587))
        self.assertEqual(
            [name for name, _, _ in server.method_calls],
            ["ehlo", "starttls", "ehlo", "login", "send_message"],
        )
        self.assertIsInstance(server.starttls.call_args[1]["context"], ssl.SSLContext)
        server.login.assert_called_once_with(
            main.EMAIL_SENDER_ADDRESS, main.EMAIL_SENDER_APP_PASSWORD
        )
        # the session is ended by the context manager rather than an explicit quit
        mock_smtp.return_value.__exit__.assert_called_once()

    @patch("smtplib.SMTP")
    def test_propagates_a_send_failure_and_still_ends_the_session(self, mock_smtp):
        server = mock_smtp.return_value.__enter__.return_value
        server.send_message.side_effect = Exception("550 rejected")

        with patch("builtins.print"):
            with self.assertRaises(Exception) as caught:
                main.useTLS()

        self.assertEqual(str(caught.exception), "550 rejected")
        mock_smtp.return_value.__exit__.assert_called_once()

    @patch("smtplib.SMTP", side_effect=OSError("connection refused"))
    def test_surfaces_the_original_error_when_the_connection_fails(self, mock_smtp):
        # a failed connect used to be masked by UnboundLocalError from the
        # finally block referencing an unassigned server (issue #4)
        with patch("builtins.print"):
            with self.assertRaises(OSError) as caught:
                main.useTLS()

        self.assertEqual(str(caught.exception), "connection refused")


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

    def test_eof_or_ctrl_c_at_the_prompt_exits_nonzero_without_connecting(self):
        for interruption in (EOFError, KeyboardInterrupt):
            with self.subTest(interruption=interruption.__name__):
                with patch("builtins.input", side_effect=interruption), patch.object(
                    main, "useSSL"
                ) as mock_ssl, patch.object(main, "useTLS") as mock_tls, patch(
                    "builtins.print"
                ) as mock_print:
                    with self.assertRaises(SystemExit) as caught:
                        main.run()
                self.assertEqual(caught.exception.code, 1)
                mock_ssl.assert_not_called()
                mock_tls.assert_not_called()
                mock_print.assert_called_once_with(
                    "\nNo answer given! Exiting without sending."
                )

    def test_a_failed_ssl_send_reports_and_exits_nonzero(self):
        with patch("builtins.input", return_value="s"), patch.object(
            main, "useSSL", side_effect=Exception("535 auth rejected")
        ), patch("builtins.print") as mock_print:
            with self.assertRaises(SystemExit) as caught:
                main.run()
        self.assertEqual(caught.exception.code, 1)
        mock_print.assert_called_once_with("Failed to send email: 535 auth rejected")

    def test_a_failed_tls_send_reports_and_exits_nonzero(self):
        with patch("builtins.input", return_value="t"), patch.object(
            main, "useTLS", side_effect=OSError("connection refused")
        ), patch("builtins.print") as mock_print:
            with self.assertRaises(SystemExit) as caught:
                main.run()
        self.assertEqual(caught.exception.code, 1)
        mock_print.assert_called_once_with("Failed to send email: connection refused")


if __name__ == "__main__":
    unittest.main()
