import os
import random
import smtplib, ssl

# email credentials
if os.environ.get("EMAIL_SENDER_ADDRESS") is None:
    print("EMAIL_SENDER_ADDRESS environment variable not set!")
    exit(1)
if os.environ.get("EMAIL_SENDER_APP_PASSWORD") is None:
    print("EMAIL_SENDER_APP_PASSWORD environment variable not set!")
    exit(1)
if os.environ.get("EMAIL_RECIPIENT") is None:
    print("EMAIL_RECIPIENT environment variable not set!")
    exit(1)
EMAIL_SENDER_ADDRESS = os.environ.get("EMAIL_SENDER_ADDRESS")
EMAIL_SENDER_APP_PASSWORD = os.environ.get("EMAIL_SENDER_APP_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

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
    return messages[random.randint(0, len(messages) - 1)]

def useSSL():
    print("Logging in with SSL...")
    smtp_server = "smtp.gmail.com"
    port = 465

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(EMAIL_SENDER_ADDRESS, EMAIL_SENDER_APP_PASSWORD)
        print("Login successful!")

        # send email
        subject = "Test email from Python"
        body = getRandomMessage()
        sendEmail(server, EMAIL_SENDER_ADDRESS, EMAIL_RECIPIENT, subject, body)

def useTLS():
    print("Logging in with TLS...")
    smtp_server = "smtp.gmail.com"
    port = 587

    sender = EMAIL_SENDER_ADDRESS
    password = EMAIL_SENDER_APP_PASSWORD

    context = ssl.create_default_context()

    # the context manager quits the session on every path out of the block
    with smtplib.SMTP(smtp_server, port) as server:
        server.ehlo() # say hello to server
        server.starttls(context=context) # start TLS encryption
        server.ehlo() # say hello again
        server.login(sender, password)
        print("Login successful!")

        # send email
        subject = "Test email from Python"
        body = getRandomMessage()
        sendEmail(server, sender, EMAIL_RECIPIENT, subject, body)

def sendEmail(server, sender, receiver, subject, body):
    message = f"From: {sender}\nTo: {receiver}\nSubject: {subject}\n\n{body}"
    server.sendmail(sender, receiver, message)
    print("Email sent to " + receiver + "!")

def run():
    user_input = input("Use SSL or TLS? (s/t): ")
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