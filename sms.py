import os
from twilio.rest import Client

_client = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(
            os.environ["TWILIO_ACCOUNT_SID"],
            os.environ["TWILIO_AUTH_TOKEN"],
        )
    return _client


def send_sms(to: str, body: str) -> str:
    msg = get_client().messages.create(
        body=body,
        from_=os.environ["TWILIO_PHONE_NUMBER"],
        to=to,
    )
    return msg.sid
