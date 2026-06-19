import logging
import re
from typing import Any, Mapping, Optional

import apprise
import httpx

from src.config import settings
from src.models import TelegramWebhookDeleteResponse, TelegramWebhookSetResponse
from src.notifiers.base import AbstractNotifier
from src.repositories import user_notifications as user_notifications_repo

logger = logging.getLogger(__name__)

START_TOKEN_PATTERN = re.compile(r"(?:^|[?&\s=])start(?:app)?=?(?P<token>[A-Za-z0-9_-]{6,})")


class TelegramNotifier(AbstractNotifier):
    channel = "telegram"

    def can_send(self, profile: Mapping[str, Any]) -> bool:
        return bool(profile.get("telegram_enabled") and profile.get("telegram_chat_id"))

    async def send(self, profile: Mapping[str, Any], title: str, body: str) -> bool:
        chat_id = profile.get("telegram_chat_id")
        if chat_id is None:
            return False
        return await self.send_message(chat_id=str(chat_id), text=body, title=title)

    @staticmethod
    def _extract_start_token(text: str, command_parts: list[str]) -> Optional[str]:
        """Extract deep-link token from common /start message formats."""
        if len(command_parts) >= 2 and command_parts[1].strip():
            return command_parts[1].strip()

        match = START_TOKEN_PATTERN.search(text)
        if match:
            return match.group("token").strip()

        return None

    def is_valid_webhook_secret(self, received_secret: Optional[str]) -> bool:
        _ = received_secret
        return True

    def get_token_from_apprise_urls(self) -> Optional[str]:
        """Extract Telegram bot token from APPRISE_URLS.

        Expected entry format inside APPRISE_URLS:
          tgram://<bot_token>/<chat_id>
        """
        if not settings.apprise_urls:
            return None

        for raw_url in settings.apprise_urls.split(","):
            url = raw_url.strip()
            if not url.lower().startswith("tgram://"):
                continue

            token_part = url[len("tgram://") :].split("/", maxsplit=1)[0].strip()
            if token_part:
                return token_part

        return None

    def _build_api_base(self) -> str:
        bot_token = self.get_token_from_apprise_urls()
        if not bot_token:
            raise RuntimeError(
                "Telegram bot token is unavailable. Add a tgram://<bot_token>/<chat_id> URL to APPRISE_URLS"
            )
        return f"https://api.telegram.org/bot{bot_token}"

    @staticmethod
    def _build_webhook_url(public_url: str) -> str:
        candidate = public_url.strip()
        if not candidate:
            raise ValueError("public_url is required")
        if not candidate.startswith(("http://", "https://")):
            raise ValueError("public_url must start with http:// or https://")
        return f"{candidate.rstrip('/')}/webhooks/telegram"

    @staticmethod
    def _extract_webhook_info(result: dict) -> tuple[Optional[str], Optional[int], Optional[str]]:
        url = result.get("url") if isinstance(result.get("url"), str) else None
        if url == "":
            url = None
        pending_update_count = result.get("pending_update_count")
        last_error_message = result.get("last_error_message")
        return url, pending_update_count, last_error_message

    async def send_message(self, chat_id: str, text: str, title: str = "Schedula Notification") -> bool:
        """Send plain text to Telegram using Apprise to keep all sending paths unified."""
        bot_token = self.get_token_from_apprise_urls()
        if not bot_token:
            logger.warning("Cannot send Telegram message because APPRISE_URLS has no Telegram token")
            return False

        url = f"tgram://{bot_token}/{chat_id}"
        sender = apprise.Apprise()
        sender.add(url)

        try:
            result = await sender.async_notify(body=text, title=title)
        except Exception as exc:
            logger.error("Failed sending Telegram message via Apprise: %s", exc)
            return False

        if not result:
            logger.warning(
                "Apprise reported delivery failure for Telegram message to chat_id=%s",
                chat_id,
            )
            return False

        return True

    async def set_webhook(self, public_url: str, secret_token: Optional[str] = None) -> TelegramWebhookSetResponse:
        telegram_api_base = self._build_api_base()
        webhook_url = self._build_webhook_url(public_url)

        payload = {"url": webhook_url}
        if secret_token:
            payload["secret_token"] = secret_token

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            set_resp = await client.post(f"{telegram_api_base}/setWebhook", json=payload)
            if set_resp.status_code != 200:
                raise RuntimeError(f"Telegram setWebhook failed with status {set_resp.status_code}")

            set_data = set_resp.json()
            if not set_data.get("ok"):
                raise RuntimeError(f"Telegram setWebhook error: {set_data}")

            info_resp = await client.get(f"{telegram_api_base}/getWebhookInfo")
            if info_resp.status_code != 200:
                raise RuntimeError(f"Telegram getWebhookInfo failed with status {info_resp.status_code}")

            info_data = info_resp.json().get("result", {})

        _, pending_update_count, last_error_message = self._extract_webhook_info(info_data)
        return TelegramWebhookSetResponse(
            telegram_ok=True,
            description=set_data.get("description"),
            webhook_url=webhook_url,
            pending_update_count=pending_update_count,
            last_error_message=last_error_message,
        )

    async def delete_webhook(self, drop_pending_updates: bool = False) -> TelegramWebhookDeleteResponse:
        telegram_api_base = self._build_api_base()

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            before_resp = await client.get(f"{telegram_api_base}/getWebhookInfo")
            if before_resp.status_code != 200:
                raise RuntimeError(f"Telegram getWebhookInfo failed with status {before_resp.status_code}")
            before_data = before_resp.json().get("result", {})
            previous_webhook_url, _, _ = self._extract_webhook_info(before_data)

            delete_resp = await client.post(
                f"{telegram_api_base}/deleteWebhook",
                json={"drop_pending_updates": drop_pending_updates},
            )
            if delete_resp.status_code != 200:
                raise RuntimeError(f"Telegram deleteWebhook failed with status {delete_resp.status_code}")

            delete_data = delete_resp.json()
            if not delete_data.get("ok"):
                raise RuntimeError(f"Telegram deleteWebhook error: {delete_data}")

            after_resp = await client.get(f"{telegram_api_base}/getWebhookInfo")
            if after_resp.status_code != 200:
                raise RuntimeError(f"Telegram getWebhookInfo failed with status {after_resp.status_code}")
            after_data = after_resp.json().get("result", {})
            webhook_url, pending_update_count, last_error_message = self._extract_webhook_info(after_data)

        return TelegramWebhookDeleteResponse(
            telegram_ok=True,
            description=delete_data.get("description"),
            previous_webhook_url=previous_webhook_url,
            webhook_url=webhook_url,
            pending_update_count=pending_update_count,
            last_error_message=last_error_message,
        )

    async def ensure_webhook_registration(self) -> None:
        logger.info("Telegram webhook auto-registration is disabled; configure webhook explicitly via backend route")

    async def handle_update(self, data: dict) -> dict:
        update_id = data.get("update_id")
        message = data.get("message") or data.get("edited_message") or data.get("channel_post") or {}
        text = str(message.get("text", "")).strip()
        chat = message.get("chat", {})
        chat_id = chat.get("id")

        if not chat_id:
            logger.info("Ignoring Telegram update without chat_id. update_id=%s keys=%s", update_id, list(data.keys()))
            return {"status": "ok"}

        str_chat_id = str(chat_id)

        if not text.startswith("/"):
            logger.info("Ignoring non-command Telegram update. update_id=%s", update_id)
            return {"status": "ok"}

        command_parts = text.split()
        command_with_bot = command_parts[0].strip().lower()
        command = command_with_bot.split("@", maxsplit=1)[0]

        if command == "/link":
            if len(command_parts) != 3:
                await self.send_message(
                    str_chat_id,
                    "To link your Schedula account, send:\n/link <user_name> <user_id>",
                )
                return {"status": "ok"}

            user_name = command_parts[1].strip()
            user_id = command_parts[2].strip()

            if not user_id.isdigit() or len(user_id) != 9:
                await self.send_message(
                    str_chat_id,
                    "Invalid user_id format. Please send:\n/link <user_name> <9-digit user_id>",
                )
                return {"status": "ok"}

            result = await user_notifications_repo.link_chat_by_credentials(user_name, user_id, str_chat_id)
            if result["success"]:
                logger.info(
                    "Linked Telegram via /link chat_id=%s user_internal_id=%s update_id=%s",
                    str_chat_id,
                    result["user_internal_id"],
                    update_id,
                )
                await self.send_message(str_chat_id, "Your Schedula account has been linked successfully.")
            else:
                await self.send_message(
                    str_chat_id,
                    "Could not validate your credentials. Check user_name and user_id, then try again.",
                )

            return {"status": "ok"}

        if command != "/start":
            return {"status": "ok"}

        token = self._extract_start_token(text, command_parts)
        if not token:
            logger.info("Received Telegram /start without token. update_id=%s text=%s", update_id, text)
            await self.send_message(
                str_chat_id,
                "No linking token was provided. Open Telegram from Schedula again or send:\n/link <user_name> <user_id>",
            )
            return {"status": "ok"}

        result = await user_notifications_repo.link_chat_by_token(
            token,
            str_chat_id,
            max_age_seconds=settings.telegram_link_token_ttl_seconds,
        )
        if result["success"]:
            logger.info(
                "Linked Telegram via /start token for chat_id=%s user_internal_id=%s update_id=%s",
                str_chat_id,
                result["user_internal_id"],
                update_id,
            )
            await self.send_message(
                str_chat_id,
                "Your Schedula account has been successfully linked. You will now receive notifications here.",
                title="Account Linked",
            )
        else:
            logger.info("Telegram /start token was rejected. update_id=%s chat_id=%s", update_id, str_chat_id)
            await self.send_message(
                str_chat_id,
                "This link token is not valid anymore. Open a fresh link from Schedula or send:\n/link <user_name> <user_id>",
            )

        return {"status": "ok"}
