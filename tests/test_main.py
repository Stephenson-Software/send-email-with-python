import os
import runpy
import shutil
import ssl
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, call, patch

# main.py reads these at import time and exits when one is missing,
# so they have to be set before the import below
os.environ.setdefault("EMAIL_SENDER_ADDRESS", "sender@example.com")
os.environ.setdefault("EMAIL_SENDER_APP_PASSWORD", "dummy-app-password")
os.environ.setdefault("EMAIL_RECIPIENT", "recipient@example.com")

# src/ is not a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main

MAIN_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "main.py")
RUN_SH_PATH = os.path.join(os.path.dirname(__file__), "..", "run.sh")
CREDENTIAL_VARIABLES = [
    "EMAIL_SENDER_ADDRESS",
    "EMAIL_SENDER_APP_PASSWORD",
    "EMAIL_RECIPIENT",
]


class TestCredentialGuards(unittest.TestCase):
    # the guards run at import time, so main.py is re-executed with one
    # or more variables removed or replaced rather than exercised through the imported module
    def run_main_without(self, *variables, value=None):
        with patch.dict(os.environ), patch(
            "builtins.input", side_effect=AssertionError("prompted")
        ) as mock_input, patch(
            "smtplib.SMTP", side_effect=AssertionError("connected")
        ) as mock_smtp, patch(
            "smtplib.SMTP_SSL", side_effect=AssertionError("connected")
        ) as mock_smtp_ssl, patch(
            "builtins.print"
        ) as mock_print:
            for variable in variables:
                if value is None:
                    del os.environ[variable]
                else:
                    os.environ[variable] = value
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
                exception, mock_print = self.run_main_without(variable, value="")
                self.assertEqual(exception.code, 1)
                mock_print.assert_called_once_with(
                    variable + " environment variable not set!"
                )

    def test_each_whitespace_only_variable_is_named_and_exits_before_prompting(self):
        for variable in CREDENTIAL_VARIABLES:
            with self.subTest(variable=variable):
                exception, mock_print = self.run_main_without(variable, value=" \t ")
                self.assertEqual(exception.code, 1)
                mock_print.assert_called_once_with(
                    variable + " environment variable not set!"
                )

    def test_every_missing_empty_or_whitespace_only_variable_is_named_in_one_run(self):
        for value in (None, "", " \t "):
            with self.subTest(value=value):
                exception, mock_print = self.run_main_without(
                    *CREDENTIAL_VARIABLES, value=value
                )
                self.assertEqual(exception.code, 1)
                self.assertEqual(
                    mock_print.call_args_list,
                    [
                        call(variable + " environment variable not set!")
                        for variable in CREDENTIAL_VARIABLES
                    ],
                )

    def test_only_the_missing_variables_are_named(self):
        exception, mock_print = self.run_main_without(
            "EMAIL_SENDER_ADDRESS", "EMAIL_RECIPIENT"
        )
        self.assertEqual(exception.code, 1)
        self.assertEqual(
            mock_print.call_args_list,
            [
                call("EMAIL_SENDER_ADDRESS environment variable not set!"),
                call("EMAIL_RECIPIENT environment variable not set!"),
            ],
        )

    def test_surrounding_whitespace_is_stripped_from_the_values_used(self):
        padded = {
            "EMAIL_SENDER_ADDRESS": " padded-sender@example.com\r",
            "EMAIL_SENDER_APP_PASSWORD": "\tabcd efgh ijkl mnop\r\n",
            "EMAIL_RECIPIENT": "padded-recipient@example.com ",
        }
        with patch.dict(os.environ, padded):
            # not run as __main__, so the prompt is never reached
            module = runpy.run_path(MAIN_PATH, run_name="padded")
        self.assertEqual(module["EMAIL_SENDER_ADDRESS"], "padded-sender@example.com")
        # internal spaces are kept, since Google shows app passwords in groups
        self.assertEqual(module["EMAIL_SENDER_APP_PASSWORD"], "abcd efgh ijkl mnop")
        self.assertEqual(module["EMAIL_RECIPIENT"], "padded-recipient@example.com")


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
        mock_smtp_ssl.return_value.__exit__.assert_called_once()

    @patch("smtplib.SMTP_SSL")
    def test_propagates_a_send_failure_and_still_ends_the_session(self, mock_smtp_ssl):
        server = mock_smtp_ssl.return_value.__enter__.return_value
        server.send_message.side_effect = Exception("550 rejected")

        with patch("builtins.print"):
            with self.assertRaises(Exception) as caught:
                main.useSSL()

        self.assertEqual(str(caught.exception), "550 rejected")
        mock_smtp_ssl.return_value.__exit__.assert_called_once()

    @patch("smtplib.SMTP_SSL")
    def test_propagates_a_rejected_login_without_sending(self, mock_smtp_ssl):
        # run() relies on this reaching it to print the login hint
        server = mock_smtp_ssl.return_value.__enter__.return_value
        server.login.side_effect = main.smtplib.SMTPAuthenticationError(
            535, b"rejected"
        )

        with patch("builtins.print"):
            with self.assertRaises(main.smtplib.SMTPAuthenticationError):
                main.useSSL()

        server.send_message.assert_not_called()
        mock_smtp_ssl.return_value.__exit__.assert_called_once()

    @patch("smtplib.SMTP_SSL", side_effect=OSError("connection refused"))
    def test_surfaces_the_original_error_when_the_connection_fails(self, mock_smtp_ssl):
        with patch("builtins.print"):
            with self.assertRaises(OSError) as caught:
                main.useSSL()

        self.assertEqual(str(caught.exception), "connection refused")


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

    @patch("smtplib.SMTP")
    def test_propagates_a_rejected_login_without_sending(self, mock_smtp):
        # run() relies on this reaching it to print the login hint
        server = mock_smtp.return_value.__enter__.return_value
        server.login.side_effect = main.smtplib.SMTPAuthenticationError(
            535, b"rejected"
        )

        with patch("builtins.print"):
            with self.assertRaises(main.smtplib.SMTPAuthenticationError):
                main.useTLS()

        server.send_message.assert_not_called()
        mock_smtp.return_value.__exit__.assert_called_once()

    @patch("smtplib.SMTP")
    def test_a_failed_upgrade_stops_before_the_credentials_are_sent(self, mock_smtp):
        # logging in after a failed starttls would send the app password in plaintext
        server = mock_smtp.return_value.__enter__.return_value
        server.starttls.side_effect = main.smtplib.SMTPNotSupportedError(
            "STARTTLS extension not supported by server."
        )

        with patch("builtins.print"):
            with self.assertRaises(main.smtplib.SMTPNotSupportedError):
                main.useTLS()

        server.login.assert_not_called()
        server.send_message.assert_not_called()
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

    def test_case_and_surrounding_whitespace_are_ignored(self):
        for answer, chosen in (("S", "useSSL"), (" t\t", "useTLS"), ("T ", "useTLS")):
            with self.subTest(answer=answer):
                with patch("builtins.input", return_value=answer), patch.object(
                    main, "useSSL"
                ) as mock_ssl, patch.object(main, "useTLS") as mock_tls:
                    main.run()
                mocks = {"useSSL": mock_ssl, "useTLS": mock_tls}
                mocks.pop(chosen).assert_called_once_with()
                for other in mocks.values():
                    other.assert_not_called()

    def test_anything_else_exits_nonzero_without_connecting(self):
        with patch("builtins.input", return_value="x"), patch.object(
            main, "useSSL"
        ) as mock_ssl, patch.object(main, "useTLS") as mock_tls, patch(
            "builtins.print"
        ) as mock_print:
            with self.assertRaises(SystemExit) as caught:
                main.run()
        self.assertEqual(caught.exception.code, 1)
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

    def test_a_rejected_login_names_the_credentials_to_check(self):
        rejection = main.smtplib.SMTPAuthenticationError(
            534, b"5.7.9 Application-specific password required."
        )
        for answer, transport in (("s", "useSSL"), ("t", "useTLS")):
            with self.subTest(transport=transport):
                with patch("builtins.input", return_value=answer), patch.object(
                    main, transport, side_effect=rejection
                ), patch("builtins.print") as mock_print:
                    with self.assertRaises(SystemExit) as caught:
                        main.run()
                self.assertEqual(caught.exception.code, 1)
                self.assertEqual(
                    mock_print.call_args_list,
                    [
                        call("Failed to send email: " + str(rejection)),
                        call(
                            "Login rejected! Check EMAIL_SENDER_ADDRESS, and that "
                            "EMAIL_SENDER_APP_PASSWORD is an app password, not the "
                            "account password."
                        ),
                    ],
                )
                # the password value itself is never echoed back
                for printed in mock_print.call_args_list:
                    self.assertNotIn(main.EMAIL_SENDER_APP_PASSWORD, printed.args[0])

    def test_a_refused_recipient_names_the_recipient_variable(self):
        refusal = main.smtplib.SMTPRecipientsRefused(
            {"someone@example": (553, b"5.1.3 not a valid RFC-5321 address.")}
        )
        for answer, transport in (("s", "useSSL"), ("t", "useTLS")):
            with self.subTest(transport=transport):
                with patch("builtins.input", return_value=answer), patch.object(
                    main, transport, side_effect=refusal
                ), patch("builtins.print") as mock_print:
                    with self.assertRaises(SystemExit) as caught:
                        main.run()
                self.assertEqual(caught.exception.code, 1)
                self.assertEqual(
                    mock_print.call_args_list,
                    [
                        call("Failed to send email: " + str(refusal)),
                        call(
                            "Recipient refused! Check that EMAIL_RECIPIENT is a "
                            "valid email address."
                        ),
                    ],
                )

    def test_ctrl_c_during_the_send_exits_nonzero_without_a_traceback(self):
        for answer, transport in (("s", "useSSL"), ("t", "useTLS")):
            with self.subTest(transport=transport):
                with patch("builtins.input", return_value=answer), patch.object(
                    main, transport, side_effect=KeyboardInterrupt
                ), patch("builtins.print") as mock_print:
                    with self.assertRaises(SystemExit) as caught:
                        main.run()
                self.assertEqual(caught.exception.code, 1)
                mock_print.assert_called_once_with(
                    "\nInterrupted! The email may not have been sent."
                )


class TestRunEndToEnd(unittest.TestCase):
    # run() goes through the real transport and send functions,
    # with only the smtplib connections replaced
    def test_a_successful_send_logs_in_sends_once_and_returns_normally(self):
        for answer, transport, used, unused, port in (
            ("s", "SSL", "smtplib.SMTP_SSL", "smtplib.SMTP", 465),
            ("t", "TLS", "smtplib.SMTP", "smtplib.SMTP_SSL", 587),
        ):
            with self.subTest(answer=answer):
                with patch("builtins.input", return_value=answer), patch(
                    used
                ) as mock_used, patch(
                    unused, side_effect=AssertionError("wrong transport")
                ) as mock_unused, patch(
                    "builtins.print"
                ) as mock_print:
                    server = mock_used.return_value.__enter__.return_value
                    main.run()
                self.assertEqual(mock_used.call_args.args, ("smtp.gmail.com", port))
                mock_unused.assert_not_called()
                server.login.assert_called_once_with(
                    main.EMAIL_SENDER_ADDRESS, main.EMAIL_SENDER_APP_PASSWORD
                )
                server.send_message.assert_called_once()
                message = server.send_message.call_args.args[0]
                self.assertEqual(message["From"], main.EMAIL_SENDER_ADDRESS)
                self.assertEqual(message["To"], main.EMAIL_RECIPIENT)
                self.assertIn(message.get_content().rstrip("\n"), main.messages)
                self.assertEqual(
                    mock_print.call_args_list,
                    [
                        call("Logging in with " + transport + "..."),
                        call("Login successful!"),
                        call("Email sent to " + main.EMAIL_RECIPIENT + "!"),
                    ],
                )


class TestRunScript(unittest.TestCase):
    @unittest.skipIf(shutil.which("bash") is None, "bash not available")
    def test_finds_main_py_when_launched_outside_the_repository_root(self):
        # with the credentials removed, reaching main.py means its guards
        # name all three and exit 1 before any prompt or connection
        env = {k: v for k, v in os.environ.items() if k not in CREDENTIAL_VARIABLES}
        result = subprocess.run(
            ["bash", os.path.abspath(RUN_SH_PATH)],
            cwd=os.path.dirname(__file__),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            result.stdout,
            "".join(
                variable + " environment variable not set!\n"
                for variable in CREDENTIAL_VARIABLES
            ),
        )


class TestWithoutSite(unittest.TestCase):
    # -S skips the site module, which is what defines the bare exit()
    def run_main_without_site(self, env, stdin):
        return subprocess.run(
            [sys.executable, "-S", os.path.abspath(MAIN_PATH)],
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
        )

    def test_missing_credentials_exit_1_without_a_traceback(self):
        env = {k: v for k, v in os.environ.items() if k not in CREDENTIAL_VARIABLES}
        result = self.run_main_without_site(env, "")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")

    def test_invalid_input_exits_1_without_a_traceback(self):
        # the answer is rejected before any connection is attempted
        result = self.run_main_without_site(dict(os.environ), "x\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        self.assertIn("Invalid input! Please type 's' or 't'.", result.stdout)


if __name__ == "__main__":
    unittest.main()
