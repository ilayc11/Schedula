import logging
from urllib.parse import quote, urlencode
from typing import Any, Mapping

import apprise

from src.config import settings
from src.notifiers.base import AbstractNotifier

logger = logging.getLogger(__name__)


class EmailAppriseNotifier(AbstractNotifier):
    """Email notifier powered by Apprise mailto:// URLs."""

    channel = "email"
    _warned_missing_config = False
    _valid_secure_modes = {"insecure", "starttls", "ssl"}

    def _resolve_sender_identity(self) -> tuple[str, str]:
        username = settings.email_sender_username.strip()
        fallback_domain = settings.email_sender_domain.strip() or "gmail.com"

        if "@" in username:
            local_part, domain = username.split("@", maxsplit=1)
            return local_part.strip(), (domain.strip() or fallback_domain)

        return username, fallback_domain

    @staticmethod
    def _normalize_app_password(password: str) -> str:
        # Gmail app passwords are shown in grouped chunks; remove spaces safely.
        return "".join(password.split())

    def _is_configured(self) -> bool:
        local_part, domain = self._resolve_sender_identity()
        app_password = self._normalize_app_password(settings.email_sender_app_password)
        return bool(local_part and domain and app_password)

    def _build_url(self, recipient_email: str) -> str:
        local_part, domain = self._resolve_sender_identity()
        app_password = self._normalize_app_password(settings.email_sender_app_password)

        from_address = settings.email_from_address.strip() or f"{local_part}@{domain}"
        smtp_host = settings.email_smtp_host.strip() or f"smtp.{domain}"
        secure_mode = settings.email_smtp_mode.strip().lower() or "starttls"
        if secure_mode not in self._valid_secure_modes:
            secure_mode = "starttls"

        query_params = {
            "from": from_address,
            "smtp": smtp_host,
            "mode": secure_mode,
        }
        from_name = settings.email_from_name.strip()
        if from_name:
            query_params["name"] = from_name

        query = urlencode(query_params)
        return (
            f"mailto://{quote(local_part, safe='')}:{quote(app_password, safe='')}"
            f"@{quote(domain, safe='')}:{int(settings.email_smtp_port)}"
            f"/{quote(recipient_email, safe='@')}?{query}"
        )

    def can_send(self, profile: Mapping[str, Any]) -> bool:
        if not self._is_configured():
            if not self._warned_missing_config:
                logger.warning(
                    "Email notifier disabled: missing EMAIL_SENDER_USERNAME and/or EMAIL_SENDER_APP_PASSWORD"
                )
                self._warned_missing_config = True
            return False

        recipient_email = str(profile.get("email") or "").strip()
        email_enabled = bool(profile.get("email_enabled", True))
        return bool(email_enabled and recipient_email)

    async def send(self, profile: Mapping[str, Any], title: str, body: str) -> bool:
        if not self.can_send(profile):
            return False

        recipient_email = str(profile.get("email")).strip()
        sender = apprise.Apprise()
        if not sender.add(self._build_url(recipient_email)):
            logger.error(
                "Failed to configure Apprise email URL for user_internal_id=%s",
                profile.get("user_internal_id"),
            )
            return False

        try:
            result = await sender.async_notify(body=body, title=title)
        except Exception as exc:
            logger.error(
                "Failed sending email notification to %s for user_internal_id=%s: %s",
                recipient_email,
                profile.get("user_internal_id"),
                exc,
            )
            return False

        # Apprise returns False (without raising) when delivery fails, e.g. SMTP
        # connection refused or rate-limited. Treat that as a failure so the
        # delivery summary and downstream metrics are accurate.
        if not result:
            logger.warning(
                "Apprise reported delivery failure for email to %s (user_internal_id=%s)",
                recipient_email,
                profile.get("user_internal_id"),
            )
            return False

        return True
