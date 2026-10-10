import os
import random
import smtplib, ssl
from email.message import EmailMessage

# email credentials (an empty value counts as not set)
if not os.environ.get("EMAIL_SENDER_ADDRESS"):
    print("EMAIL_SENDER_ADDRESS environment variable not set!")
    exit(1)
if not os.environ.get("EMAIL_SENDER_APP_PASSWORD"):
    print("EMAIL_SENDER_APP_PASSWORD environment variable not set!")
    exit(1)
if not os.environ.get("EMAIL_RECIPIENT"):
    print("EMAIL_RECIPIENT environment variable not set!")
    exit(1)
EMAIL_SENDER_ADDRESS = os.environ.get("EMAIL_SENDER_ADDRESS")
EMAIL_SENDER_APP_PASSWORD = os.environ.get("EMAIL_SENDER_APP_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

# gmail smtp endpoint and subject shared by both transports
SMTP_HOST = "smtp.gmail.com"
SMTP_SSL_PORT = 465
SMTP_TLS_PORT = 587
EMAIL_SUBJECT = "Test email from Python"

# list of messages to send
messages = [
    "The purple elephant danced wildly on the flying pizza.",
    "The talking cactus told me to wear a hat made of spaghetti.",
    "The moon sings lullabies to the sleeping sun.",
    "The clock went for a walk in the park with a rubber duck.",
    "The library is full of singing donuts with wings.",
    "The rainbow tasted like cotton candy and smelled like sunshine.",
    "The trees have started to dance, and the squirrels are cheering them on.",
    "The broccoli turned into a butterfly and flew away.",
    "The ocean waves whispered secrets to the seagulls.",
    "The clouds played a game of tag with the airplanes in the sky."
]

def getRandomMessage():
    return random.choice(messages)

def useSSL():
    print("Logging in with SSL...")
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_SSL_PORT, context=context) as server:
        server.login(EMAIL_SENDER_ADDRESS, EMAIL_SENDER_APP_PASSWORD)
        print("Login successful!")
        sendRandomMessage(server)

def useTLS():
    print("Logging in with TLS...")
    context = ssl.create_default_context()

    # the context manager quits the session on every path out of the block
    with smtplib.SMTP(SMTP_HOST, SMTP_TLS_PORT) as server:
        server.ehlo() # say hello to server
        server.starttls(context=context) # start TLS encryption
        server.ehlo() # say hello again
        server.login(EMAIL_SENDER_ADDRESS, EMAIL_SENDER_APP_PASSWORD)
        print("Login successful!")
        sendRandomMessage(server)

def sendRandomMessage(server):
    # send one of the messages above over an already logged-in session
    sendEmail(server, EMAIL_SENDER_ADDRESS, EMAIL_RECIPIENT, EMAIL_SUBJECT, getRandomMessage())

def sendEmail(server, sender, receiver, subject, body):
    # headers are set individually so a newline in one is rejected, not injected
    message = EmailMessage()
    message["From"] = sender
    message["To"] = receiver
    message["Subject"] = subject
    message.set_content(body)
    server.send_message(message)
    print("Email sent to " + receiver + "!")

def run():
    # closed stdin or ctrl-c at the prompt ends the run without connecting
    try:
        user_input = input("Use SSL or TLS? (s/t): ")
    except (EOFError, KeyboardInterrupt):
        print("\nNo answer given! Exiting without sending.")
        exit(1)
    if user_input == "s":
        transport = useSSL
    elif user_input == "t":
        transport = useTLS
    else:
        print("Invalid input! Please type 's' or 't'.")
        return

    # a failed send must not look like a successful run
    try:
        transport()
    except Exception as e:
        print(f"Failed to send email: {e}")
        exit(1)

if __name__ == "__main__":
    run()