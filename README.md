# Send Email With Python
This repository is for practicing sending email with python.

## Requirements
- Python 3 (only the standard library is used — nothing to install)
- A Gmail account with 2-Step Verification enabled and an [app password](https://support.google.com/accounts/answer/185833) generated for it

## Configuration
Three environment variables are read at startup. If any are missing, empty, or only whitespace, the program names every one of them and exits with status 1 before any connection is attempted. Leading and trailing whitespace (such as a stray space or a `\r` from a file saved with Windows line endings) is stripped from each value before it is used; spaces inside a value are kept.

| Variable | Description |
| --- | --- |
| `EMAIL_SENDER_ADDRESS` | The Gmail address the message is sent from |
| `EMAIL_SENDER_APP_PASSWORD` | The 16-character app password for that account — **not** the account password |
| `EMAIL_RECIPIENT` | The address the message is sent to |

```bash
export EMAIL_SENDER_ADDRESS="you@gmail.com"
export EMAIL_SENDER_APP_PASSWORD="abcdefghijklmnop"
export EMAIL_RECIPIENT="someone@example.com"
```

## Usage
```bash
./run.sh
```

`run.sh` finds `src/main.py` relative to its own location, so it can be run from any directory (e.g. `path/to/send-email-with-python/run.sh`).

Or without the wrapper script, from the repository root:

```bash
python3 src/main.py
```

Either way the following prompt appears:

```
Use SSL or TLS? (s/t): 
```

The answer is case-insensitive and surrounding whitespace is ignored, so `S` or ` t ` work too.

- `s` — connects to `smtp.gmail.com:465` over SSL
- `t` — connects to `smtp.gmail.com:587` and upgrades the connection with STARTTLS
- Anything else — prints `Invalid input! Please type 's' or 't'.` and exits with status 1 without connecting
- No answer (Ctrl-C, Ctrl-D, or a closed stdin) — prints `No answer given! Exiting without sending.` and exits with status 1 without connecting

Both answers log in to Gmail and send a real email containing one randomly chosen message from the list in `src/main.py`.

If the send fails — an unreachable server, a rejected login, a refused recipient — the reason is printed as `Failed to send email: <reason>` and the program exits with status 1, so `run.sh` reports the failure rather than a success. When Gmail rejects the login specifically, a second line follows: `Login rejected! Check EMAIL_SENDER_ADDRESS, and that EMAIL_SENDER_APP_PASSWORD is an app password, not the account password.` Pressing Ctrl-C while connecting or sending prints `Interrupted! The email may not have been sent.` and also exits with status 1.

## Tests
The test suite uses the standard library's `unittest` module and mocks every SMTP
connection, so running it sends no email and opens no socket. From the repository root:

```bash
python3 -m unittest discover -s tests -t .
```

## Relevant Links
- https://realpython.com/python-send-email/
- https://realpython.com/lessons/sending-emails-intro-and-account-configuration/
