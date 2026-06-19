from typing import Dict
from fastapi import APIRouter, HTTPException
from aio_pika import Message
import json
from datetime import datetime
import uuid

from src.rabbitmq.rabbitmq import rabbitmq

router = APIRouter(prefix="/rabbitmq", tags=["rabbitmq"])

REQUEST_QUEUE_NAME = "constraints_request_queue"
RESPONSE_QUEUE_NAME = "constraints_response_queue"



@router.get(
    "/health",
    responses={
        200: {
            "description": "RabbitMQ is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "connected": True,
                        "channel_open": True
                    }
                }
            },
        },
        503: {
            "description": "RabbitMQ is not healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "connected": False,
                        "error": "Connection not established"
                    }
                }
            },
        },
    },
)
async def rabbitmq_health() -> Dict[str, object]:
    """Check RabbitMQ connection health"""
    try:
        is_connected = rabbitmq.connection is not None and not rabbitmq.connection.is_closed
        is_channel_open = rabbitmq.channel is not None and not rabbitmq.channel.is_closed
        
        if is_connected and is_channel_open:
            return {
                "status": "healthy",
                "connected": is_connected,
                "channel_open": is_channel_open
            }
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "unhealthy",
                    "connected": is_connected,
                    "channel_open": is_channel_open
                }
            )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }
        )
@router.post(
    "/publish",
    responses={
        200: {
            "description": "Message published successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "published",
                        "queue": "constraints_queue",
                        "message": "Test message",
                        "correlation_id": "uuid-here"
                    }
                }
            },
        },
        400: {
            "description": "Failed to publish message",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to publish message"}
                }
            },
        },
    },
)
async def publish_message(message: str) -> Dict[str, str]:
    """Publish a message to the constraints queue"""
    try:
        channel = rabbitmq.get_channel()
        
        # Declare both queues
        await channel.declare_queue(REQUEST_QUEUE_NAME, durable=True)
        await channel.declare_queue(RESPONSE_QUEUE_NAME, durable=True)
        
        # Generate correlation ID for request-response tracking
        correlation_id = str(uuid.uuid4())
        
        # Create message with metadata
        msg_body = {
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "backend_api_publish",
            "correlation_id": correlation_id
        }
        
        # Publish message
        await channel.default_exchange.publish(
            Message(
                body=json.dumps(msg_body).encode(),
                correlation_id=correlation_id,
                reply_to=RESPONSE_QUEUE_NAME
            ),
            routing_key=REQUEST_QUEUE_NAME
        )
        
        return {
            "status": "published",
            "queue": REQUEST_QUEUE_NAME,
            "message": message,
            "correlation_id": correlation_id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/consume-response",
    responses={
        200: {
            "description": "Response consumed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "consumed",
                        "queue": "constraints_response_queue",
                        "message": {"result": "processed", "timestamp": "2025-11-30T12:00:00"},
                        "correlation_id": "uuid-here",
                        "queue_size": 0
                    }
                }
            },
        },
        404: {
            "description": "No responses in queue",
            "content": {
                "application/json": {
                    "example": {"detail": "No responses available in queue"}
                }
            },
        },
    },
)
async def consume_response() -> Dict[str, object]:
    """Consume a response from the response queue"""
    try:
        channel = rabbitmq.get_channel()
        
        # Declare queue (idempotent)
        queue = await channel.declare_queue(RESPONSE_QUEUE_NAME, durable=True)
        
        # Get one message
        message = await queue.get(fail=False)
        
        if message is None:
            raise HTTPException(status_code=404, detail="No responses available in queue")
        
        # Decode and parse message
        msg_body = json.loads(message.body.decode())
        
        # Acknowledge message
        await message.ack()
        
        # Get updated queue size
        queue_info = await channel.declare_queue(RESPONSE_QUEUE_NAME, durable=True, passive=True)
        
        return {
            "status": "consumed",
            "queue": RESPONSE_QUEUE_NAME,
            "message": msg_body,
            "correlation_id": message.correlation_id,
            "queue_size": queue_info.declaration_result.message_count
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/queue-info",
    responses={
        200: {
            "description": "Queue information",
            "content": {
                "application/json": {
                    "example": {
                        "queue": "constraints_queue",
                        "message_count": 5,
                        "consumer_count": 0
                    }
                }
            },
        },
        400: {
            "description": "Failed to get queue info",
            "content": {
                "application/json": {
                    "example": {"detail": "Queue does not exist"}
                }
            },
        },
    },
)
async def get_queue_info() -> Dict[str, object]:
    """Get information about the constraints queue"""
    try:
        channel = rabbitmq.get_channel()
        
        # Declare queue in passive mode (doesn't create if doesn't exist)
        queue = await channel.declare_queue(REQUEST_QUEUE_NAME, durable=True)
        
        return {
            "queue": REQUEST_QUEUE_NAME,
            "message_count": queue.declaration_result.message_count,
            "consumer_count": queue.declaration_result.consumer_count
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
