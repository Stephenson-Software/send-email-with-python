# Send Email With Python
This repository is for practicing sending email with python.

## Requirements
- Python 3 (only the standard library is used — nothing to install)
- A Gmail account with 2-Step Verification enabled and an [app password](https://support.google.com/accounts/answer/185833) generated for it

## Configuration
Three environment variables are read at startup. If any is missing, the program prints which one and exits with status 1 before any connection is attempted.

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

Or without the wrapper script:

```bash
python3 src/main.py
```

Either way the following prompt appears:

```
Use SSL or TLS? (s/t): 
```

- `s` — connects to `smtp.gmail.com:465` over SSL
- `t` — connects to `smtp.gmail.com:587` and upgrades the connection with STARTTLS
- Anything else — prints `Invalid input! Please type 's' or 't'.` and exits without connecting

Both answers log in to Gmail and send a real email containing one randomly chosen message from the list in `src/main.py`.

## Relevant Links
- https://realpython.com/python-send-email/
- https://realpython.com/lessons/sending-emails-intro-and-account-configuration/
