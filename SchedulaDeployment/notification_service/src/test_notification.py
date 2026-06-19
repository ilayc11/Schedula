import asyncio
import json
import logging
import os
from dotenv import load_dotenv
from aio_pika import connect, Message

# Load environment variables
load_dotenv()

# Configuration
# Default to localhost for running from host.
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://rabbitmq:rabbitmq@localhost:5672/")
NOTIFICATION_QUEUE_NAME = "notifications_queue"
TARGET_USER_INTERNAL_ID = os.getenv("TARGET_USER_INTERNAL_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info(f"Connecting to RabbitMQ at {RABBITMQ_URL}")
    try:
        connection = await connect(RABBITMQ_URL)
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        return

    async with connection:
        channel = await connection.channel()
        
        # Ensure queue exists
        await channel.declare_queue(NOTIFICATION_QUEUE_NAME, durable=True)

        if not TARGET_USER_INTERNAL_ID:
            logger.error("TARGET_USER_INTERNAL_ID is not set in environment variables.")
            return

        try:
            target_user_id = int(TARGET_USER_INTERNAL_ID)
        except ValueError:
            logger.error("TARGET_USER_INTERNAL_ID must be an integer.")
            return

        message_body = {
            "schema_version": "2.0",
            "message_type": "manual_test",
            "recipient_user_ids": [target_user_id],
            "metadata": {
                "event_type": "manual_test"
            },
            "payload": {
                "title": "Schedula Update",
                "body": "Your schedule generation is complete. Check the dashboard for details.",
                "urls": []
            }
        }

        logger.info("Sending notification for recipient user_internal_id=%s", target_user_id)
        
        await channel.default_exchange.publish(
            Message(
                body=json.dumps(message_body).encode(),
            ),
            routing_key=NOTIFICATION_QUEUE_NAME
        )
        
        logger.info("Message published to queue.")

if __name__ == "__main__":
    asyncio.run(main())
