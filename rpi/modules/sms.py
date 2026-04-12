# modules/sms.py — SMS via Semaphore HTTP API
#
# Sends ONE notification when all slots are DRY.
# Recipient number set from dashboard and persisted across reboots.

import requests
import logging

from config import SMS_API_URL, SMS_API_KEY, SMS_SENDER

logger = logging.getLogger(__name__)


class SMSModule:
    def __init__(self):
        self.recipient  = None
        self.api_key    = SMS_API_KEY
        self._sent_once = False   # Resets each scan cycle

    def set_recipient(self, number: str):
        self.recipient = number.strip()
        logger.info(f"SMS recipient: {self.recipient}")

    def reset_sent_flag(self):
        """Call at the start of each scan cycle."""
        self._sent_once = False

    def send_drying_complete(self) -> bool:
        if self._sent_once:
            logger.info("SMS: already sent this cycle — skipping.")
            return True
        if not self.recipient:
            logger.warning("SMS: no recipient set — skipping.")
            return False
        message = (
            "✅ Smart Dryer Alert: All slots are DRY! "
            "You can collect your laundry now."
        )
        ok = self._send(self.recipient, message)
        if ok:
            self._sent_once = True
        return ok

    def send_custom(self, number: str, message: str) -> bool:
        return self._send(number, message)

    def _send(self, number: str, message: str) -> bool:
        payload = {
            "apikey":     self.api_key,
            "number":     number,
            "message":    message,
            "sendername": SMS_SENDER,
        }
        try:
            resp = requests.post(SMS_API_URL, data=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"SMS sent to {number}: HTTP {resp.status_code}")
            return True
        except requests.exceptions.ConnectionError:
            logger.error("SMS: network error — is the Pi online?")
        except requests.exceptions.Timeout:
            logger.error("SMS: request timed out.")
        except requests.exceptions.HTTPError as e:
            logger.error(f"SMS: HTTP {e}")
        except Exception as e:
            logger.error(f"SMS: unexpected error — {e}")
        return False


# Singleton
sms = SMSModule()
