#!/usr/bin/env python3
"""Mark the latest arXiv email as unread for testing."""

import imaplib
from dotenv import load_dotenv
from ai_mail_relay.config import Settings

load_dotenv()

settings = Settings()
settings.validate()

# Connect to IMAP
client = imaplib.IMAP4_SSL(settings.mailbox.imap_host, settings.mailbox.imap_port)
client.login(settings.mailbox.imap_user, settings.mailbox.imap_password)
client.select(settings.mailbox.imap_folder)

# Search for arXiv emails
criteria = f'FROM "{settings.mailbox.sender_filter}"'
status, response = client.search(None, criteria)
message_ids = response[0].decode().split()

if message_ids:
    # Mark the latest one as unread
    latest_id = message_ids[-1]
    client.store(latest_id, '-FLAGS', '\\Seen')
    print(f"Marked email ID {latest_id} as UNREAD")
else:
    print("No arXiv emails found")

client.logout()
