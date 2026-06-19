from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Notification service settings loaded from environment variables."""

    database_url: str = "postgresql://postgres:postgres@postgres:5432/schedula"
    database_pool_min_size: int = 2
    database_pool_max_size: int = 10

    rabbitmq_url: str = "amqp://rabbitmq:rabbitmq@rabbitmq:5672/"
    notification_queue_name: str = "notifications_queue"

    # Optional default target URLs for Apprise (comma-separated)
    apprise_urls: str = ""

    # Email delivery settings (Apprise mailto://)
    email_sender_username: str = ""
    email_sender_app_password: str = ""
    email_sender_domain: str = "gmail.com"
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_smtp_mode: str = "starttls"
    email_from_address: str = ""
    email_from_name: str = "Schedula"

    # Telegram linking settings
    telegram_bot_name: str = "Schedula_BotBot"
    telegram_link_token_ttl_seconds: int = 900


settings = Settings()
