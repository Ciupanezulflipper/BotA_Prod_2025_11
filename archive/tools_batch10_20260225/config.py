import os
ENV = {
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
    "VERIFY_SSL": os.getenv("VERIFY_SSL", "1") != "0",
    "CURL_BIN": os.getenv("CURL_BIN", "curl"),
    "CONF_MIN": float(os.getenv("CONF_MIN", "0.8")),
    "CONF_MIN_NEWS": float(os.getenv("CONF_MIN_NEWS", "1.2")),
}
