"""
Telegram alert sender with robust error handling.
Respects VERIFY_SSL and returns consistent (bool, str) tuples.
"""
import os
import requests
from typing import Tuple, List


def send_telegram_message(text: str) -> Tuple[bool, str]:
    """
    Send a message to Telegram channel(s).
    
    Args:
        text: Message text (markdown supported)
        
    Returns:
        (success: bool, error_message: str)
        If success=True, error_message is empty.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids_raw = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    chat_ids_list = os.getenv("TELEGRAM_CHAT_ID_LIST", "").strip()
    
    # Determine chat IDs
    chat_ids: List[str] = []
    if chat_ids_list:
        chat_ids = [cid.strip() for cid in chat_ids_list.split(",") if cid.strip()]
    elif chat_ids_raw:
        chat_ids = [chat_ids_raw]
    
    # Validate inputs
    if not token:
        return False, "TELEGRAM_BOT_TOKEN not set"
    if not chat_ids:
        return False, "TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID_LIST not set"
    
    # Determine SSL verification
    verify_ssl = os.getenv("VERIFY_SSL", "true").lower() == "true"
    
    # Send to all chat IDs
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    failures = []
    
    for chat_id in chat_ids:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        try:
            resp = requests.post(url, json=payload, timeout=10, verify=verify_ssl)
            
            if resp.status_code == 401:
                return False, "401 Unauthorized (check TELEGRAM_BOT_TOKEN)"
            elif resp.status_code == 400:
                # Bad request, likely invalid chat_id
                try:
                    err_msg = resp.json().get("description", "Bad request")
                except:
                    err_msg = "Bad request"
                failures.append(f"{chat_id}: {err_msg}")
            elif not resp.ok:
                failures.append(f"{chat_id}: HTTP {resp.status_code}")
            
        except requests.exceptions.SSLError as e:
            return False, f"SSL error (set VERIFY_SSL=false?): {e}"
        except requests.exceptions.ConnectionError as e:
            return False, f"Connection error: {e}"
        except requests.exceptions.Timeout:
            return False, "Request timeout"
        except Exception as e:
            return False, f"Unexpected error: {e}"
    
    if failures:
        return False, "; ".join(failures)
    
    return True, ""
