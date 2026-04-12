# modules/sms.py — SMS via Semaphore HTTP API
#
# Sends ONE notification when all slots are DRY.
# Recipient number and API key are set from the dashboard and
# persisted across reboots via state_store.

import requests
import logging

from config import SMS_API_URL

logger = logging.getLogger(__name__)


class SMSModule:
    def __init__(self):
        self.recipient  = None
        self._sent_once = False   # Resets each scan cycle

    def set_recipient(self, number: str):
        self.recipient = number.strip()
        logger.info(f"SMS recipient: {self.recipient}")

    def reset_sent_flag(self):
        """Call at the start of each scan cycle."""
        self._sent_once = False

    def _get_api_key(self) -> str:
        """Read the API key dynamically from persisted state."""
        import state_store
        state = state_store.load()
        key = state.get("sms_api_key", "")
        return key.strip() if key else ""

    def send_drying_complete(self) -> bool:
        if self._sent_once:
            logger.info("SMS: already sent this cycle — skipping.")
            return True
        if not self.recipient:
            logger.warning("SMS: no recipient set — skipping.")
            return False
        message = (
            "Smart Dryer Alert: All slots are DRY! "
            "You can collect your laundry now."
        )
        ok = self._send(self.recipient, message)
        if ok:
            self._sent_once = True
        return ok

    def send_custom(self, number: str, message: str) -> bool:
        return self._send(number, message)

    def _send(self, number: str, message: str) -> bool:
        api_key = self._get_api_key()
        if not api_key:
            logger.error("SMS: No API key configured. Set it in the dashboard.")
            return False

        payload = {
            "apikey":     api_key,
            "number":     number,
            "message":    message,
            "sendername": "SEMAPHORE",
        }
        try:
            logger.info(f"SMS: Sending to {number} via {SMS_API_URL}...")
            resp = requests.post(SMS_API_URL, json=payload, timeout=15)
            body = resp.text
            logger.info(f"SMS response [{resp.status_code}]: {body[:300]}")
            resp.raise_for_status()
            return True
        except requests.exceptions.ConnectionError:
            logger.error("SMS: network error — is the Pi online?")
        except requests.exceptions.Timeout:
            logger.error("SMS: request timed out (15s).")
        except requests.exceptions.HTTPError as e:
            logger.error(f"SMS: HTTP error — {e}")
        except Exception as e:
            logger.error(f"SMS: unexpected error — {e}")
        return False


# Singleton
sms = SMSModule()
