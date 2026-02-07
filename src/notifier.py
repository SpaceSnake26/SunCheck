class Notifier:
    def __init__(self, telegram_token=None, telegram_chat_id=None):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id

    def notify(self, message, tag="INFO"):
        """
        Prints to console and optionally sends a Telegram notification.
        """
        tag_icon = "[*]"
        if tag == "OPPORTUNITY": tag_icon = "!!!"
        if tag == "WATCHLIST": tag_icon = "[v]"
        
        full_msg = f"{tag_icon} [{tag}] {message}"
        print(full_msg)
        
        # Optional Telegram Integration
        if self.telegram_token and self.telegram_chat_id:
            import requests
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                payload = {"chat_id": self.telegram_chat_id, "text": full_msg}
                requests.post(url, json=payload, timeout=5)
            except Exception as e:
                print(f"Telegram notification failed: {e}")
