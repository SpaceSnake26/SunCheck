"""Notification system for SunCheck bot.

Supports console output and optional Telegram notifications.
"""
import os
import requests
from typing import Optional, Callable
from enum import Enum


class NotificationType(Enum):
    """Notification severity/type levels."""
    INFO = "INFO"
    OPPORTUNITY = "OPPORTUNITY"
    TRADE = "TRADE"
    SETTLEMENT = "SETTLEMENT"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Notifier:
    """
    Notification handler for bot events.
    
    Supports console output and optional Telegram notifications.
    """
    
    def __init__(
        self, 
        telegram_token: Optional[str] = None, 
        telegram_chat_id: Optional[str] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        # Try to load from environment if not provided
        self.telegram_token = telegram_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.log_callback = log_callback
        self.enabled = True
    
    def _get_icon(self, notif_type: NotificationType) -> str:
        """Get icon for notification type."""
        icons = {
            NotificationType.INFO: "[*]",
            NotificationType.OPPORTUNITY: "!!!",
            NotificationType.TRADE: ">>>",
            NotificationType.SETTLEMENT: "[$]",
            NotificationType.WARNING: "[!]",
            NotificationType.ERROR: "[X]",
        }
        return icons.get(notif_type, "[*]")

    def notify(
        self, 
        message: str, 
        notif_type: NotificationType = NotificationType.INFO,
        send_telegram: bool = True
    ) -> str:
        """
        Send a notification.
        
        Args:
            message: Notification message
            notif_type: Type/severity of notification
            send_telegram: Whether to send via Telegram (if configured)
        
        Returns:
            Formatted message string
        """
        if not self.enabled:
            return message
        
        icon = self._get_icon(notif_type)
        full_msg = f"{icon} [{notif_type.value}] {message}"
        
        # Console output
        print(full_msg)
        
        # Log callback (for bot_service)
        if self.log_callback:
            self.log_callback(full_msg)
        
        # Telegram notification
        if send_telegram and self.telegram_token and self.telegram_chat_id:
            self._send_telegram(full_msg)
        
        return full_msg
    
    def _send_telegram(self, message: str) -> bool:
        """Send message via Telegram bot."""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id, 
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=5)
            return response.status_code == 200
        except requests.RequestException as e:
            print(f"Telegram notification failed: {e}")
            return False
    
    # Convenience methods
    def info(self, message: str) -> str:
        """Send info notification."""
        return self.notify(message, NotificationType.INFO)
    
    def opportunity(self, message: str) -> str:
        """Send opportunity notification (always sends Telegram)."""
        return self.notify(message, NotificationType.OPPORTUNITY, send_telegram=True)
    
    def trade(self, message: str) -> str:
        """Send trade notification (always sends Telegram)."""
        return self.notify(message, NotificationType.TRADE, send_telegram=True)
    
    def settlement(self, message: str) -> str:
        """Send settlement notification."""
        return self.notify(message, NotificationType.SETTLEMENT, send_telegram=True)
    
    def warning(self, message: str) -> str:
        """Send warning notification."""
        return self.notify(message, NotificationType.WARNING)
    
    def error(self, message: str) -> str:
        """Send error notification."""
        return self.notify(message, NotificationType.ERROR, send_telegram=True)
