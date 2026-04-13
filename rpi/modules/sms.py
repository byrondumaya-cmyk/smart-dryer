# modules/sms.py — SMS via Semaphore HTTP API
#
# Sends ONE notification when all slots are DRY.
# Recipient number and API key are set from the dashboard and
# persisted across reboots via state_store.

import requests
import logging

from config import SMS_API_URL, SMS_SENDER

logger = logging.getLogger(__name__)


class SMSModule:
    def __init__(self):
        self._sent_once = False   # Resets each scan cycle

    def reset_sent_flag(self):
        """Call at the start of each scan cycle."""
        self._sent_once = False

    def _get_config(self) -> tuple:
        """Read the API key and recipients dynamically from persistent state."""
        import state_store
        state = state_store.load()
        key = state.get("sms_api_key", "").strip()
        recipients = state.get("sms_recipients", [])
        return key, [r.strip() for r in recipients if r.strip()]

    def send_drying_complete(self) -> bool:
        if self._sent_once:
            logger.info("SMS: already sent this cycle — skipping.")
            return True
            
        api_key, recipients = self._get_config()
        
        if not recipients:
            logger.warning("SMS: no recipients set — skipping.")
            return False
            
        if not api_key:
            logger.error("SMS: No API key configured. Set it in the dashboard.")
            return False

        message = (
            "Smart Dryer Alert: All slots are DRY! "
            "You can collect your laundry now."
        )
        
        success = False
        for number in recipients:
            ok = self._send(api_key, number, message)
            if ok:
                success = True
                
        if success:
            self._sent_once = True
            
        return success

    def send_custom(self, number: str, message: str) -> bool:
        api_key, _ = self._get_config()
        if not api_key:
            return False
        return self._send(api_key, number, message)

    def _send(self, api_key: str, number: str, message: str) -> bool:
        payload = {
            "apikey":     api_key,
            "number":     number,
            "message":    message,
            "sendername": SMS_SENDER,
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
