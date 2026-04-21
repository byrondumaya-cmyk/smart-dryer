# modules/sms.py — SMS via Semaphore HTTP API
#
# Sends notifications after scan cycles.
# Recipient number and API key are set from the dashboard and
# persisted across reboots via state_store.

import requests
import logging
import time

from config import SMS_API_URL, SMS_SENDER

logger = logging.getLogger(__name__)


class SMSModule:
    def __init__(self):
        self._sent_once = False   # Resets each scan cycle

    def reset_sent_flag(self):
        """Call at the start of each scan cycle."""
        self._sent_once = False
        logger.info("SMS: sent_once flag reset for new cycle.")

    def _get_config(self) -> tuple:
        """Read the API key and recipients dynamically from persistent state."""
        import state_store
        state = state_store.load()
        key = state.get("sms_api_key", "").strip()
        recipients = state.get("sms_recipients", [])
        clean = [r.strip() for r in recipients if r.strip()]
        logger.info(f"SMS: _get_config -> key_len={len(key)}, recipients={clean}")
        return key, clean

    def send_cycle_report(self, all_dry: bool, dry_count: int, wet_count: int) -> bool:
        logger.info(f"SMS: send_cycle_report called -> all_dry={all_dry}, dry={dry_count}, wet={wet_count}, sent_once={self._sent_once}")

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

        timestamp = time.strftime('%I:%M %p')

        if all_dry:
            message = (
                "Smart Dryer: All slots are DRY! "
                f"You can collect your laundry now. (T: {timestamp})"
            )
        else:
            message = (
                f"Smart Dryer Update: {dry_count} DRY, {wet_count} WET. "
                f"Drying is still in progress. (T: {timestamp})"
            )

        logger.info(f"SMS: Will send to {len(recipients)} recipient(s): {recipients}")

        success = False
        for number in recipients:
            ok = self._send(api_key, number, message)
            logger.info(f"SMS: _send result for {number} = {ok}")
            if ok:
                success = True

        if success:
            self._sent_once = True

        logger.info(f"SMS: send_cycle_report final result = {success}")
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
            logger.info(f"SMS: POST to {SMS_API_URL} for {number} ...")
            resp = requests.post(SMS_API_URL, json=payload, timeout=15)
            body = resp.text
            logger.info(f"SMS: response [{resp.status_code}]: {body[:500]}")

            if resp.status_code >= 400:
                logger.error(f"SMS: HTTP {resp.status_code} error")
                return False

            # Semaphore returns a JSON array on success, e.g. [{...}]
            # On validation errors it returns a JSON dict, e.g. {"field":["error"]}
            try:
                data = resp.json()
                if isinstance(data, dict):
                    # Check if it's actually an error dict
                    # Some error examples: {"apikey":["invalid"]}, {"status":"Error"}
                    logger.error(f"SMS: Semaphore validation error: {data}")
                    return False
            except ValueError:
                # Response wasn't JSON — unusual but message may have sent
                logger.warning(f"SMS: Response is not JSON, raw: {body[:200]}")

            logger.info(f"SMS: Successfully sent to {number}")
            return True

        except requests.exceptions.ConnectionError:
            logger.error("SMS: network error — is the Pi online?")
        except requests.exceptions.Timeout:
            logger.error("SMS: request timed out (15s).")
        except Exception as e:
            logger.error(f"SMS: unexpected error — {e}")
        return False


# Singleton
sms = SMSModule()
