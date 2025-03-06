import os
import traceback
import json
import pika
import requests
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
from database import get_line_collection, get_roi_collection

load_dotenv(find_dotenv())

RABBIT_MQ_HOST = os.getenv("RABBIT_MQ_HOST")
RABBIT_MQ_PORT = os.getenv("RABBIT_MQ_PORT")
RABBIT_MQ_USERNAME = os.getenv("RABBIT_MQ_USER")
RABBIT_MQ_PASSWORD = os.getenv("RABBIT_MQ_PASSWORD")

# RABBIT_MQ_HOST = "localhost"
# RABBIT_MQ_PORT = 5678
# RABBIT_MQ_USERNAME = "guest"
# RABBIT_MQ_PASSWORD = "guest"

ANALYTICS_RECEIVER_URL = "https://api.realsoft.ai/customer/deepstream_analytics/analytics_receiver"
# ANALYTICS_RECEIVER_URL = "http://0.0.0.0:8010/customer/deepstream_analytics/analytics_receiver"


def connect_to_rabbitmq():
    credentials = pika.PlainCredentials(RABBIT_MQ_USERNAME, RABBIT_MQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RABBIT_MQ_HOST, port=RABBIT_MQ_PORT, credentials=credentials
    )
    return pika.BlockingConnection(parameters)


rabbitmq_conn = None
conn = None

roi_collection = get_roi_collection()
line_collection = get_line_collection()

analytics_time_record = dict()


def http_send_report(
    report_id: str,
    roi_id: int,
    timestamp: str,
    number_of_people: int,
    jetson_device_id: str,
    frame_image: str,
    illegal_parking: bool = False,
):
    try:
        requests.post(
            ANALYTICS_RECEIVER_URL,
            json={
                "report_id": report_id,
                "roi_id": roi_id,
                "timestamp": timestamp,
                "number_of_people": number_of_people,
                "jetson_device_id": jetson_device_id,
                "frame_image": frame_image,
                "illegal_parking": illegal_parking,
            },
        )
    except Exception:
        pass


def handle_roi_message(message, roi_id: str, jetson_device_id: str, frame: str = None):
    try:
        payload = {}
        payload["@timestamp"] = datetime.fromisoformat(
            message["@timestamp"].rstrip("Z")
        )
        payload["event_type"] = (
            "entrance" if message["event"]["type"] == "parked" else "exit"
        )
        payload["event_id"] = message["event"]["id"]
        payload["roi_id"] = int(roi_id)
        payload["jetson_device_id"] = jetson_device_id
        payload["number_of_people"] = message["object"]["person"]["age"]
        payload["containsFrame"] = False

        if analytics_time_record.get(jetson_device_id):
            report_time_difference: timedelta = (
                datetime.now() - analytics_time_record[jetson_device_id]
            )

            if report_time_difference.seconds >= 300:
                if payload["event_type"] == "entrance" and frame is not None:
                    payload["containsFrame"] = True
                    threading.Thread(
                        target=http_send_report,
                        args=(
                            payload["event_id"],
                            payload["roi_id"],
                            payload["@timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                            payload["number_of_people"],
                            jetson_device_id,
                            frame,
                        ),
                    ).start()

                    analytics_time_record[jetson_device_id] = datetime.now()
        else:
            if payload["event_type"] == "entrance" and frame is not None:
                payload["containsFrame"] = True
                threading.Thread(
                    target=http_send_report,
                    args=(
                        payload["event_id"],
                        payload["roi_id"],
                        payload["@timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                        payload["number_of_people"],
                        jetson_device_id,
                        frame,
                    ),
                ).start()

                analytics_time_record[jetson_device_id] = datetime.now()

        roi_collection.insert_one(payload)

    except Exception:
        pass


def handle_line_message(message: str, line_id: str, jetson_device_id: str):
    try:
        payload = {}
        payload["@timestamp"] = datetime.fromisoformat(
            message["@timestamp"].rstrip("Z")
        )
        payload["event_id"] = message["event"]["id"]
        payload["line_id"] = int(line_id)
        payload["jetson_device_id"] = jetson_device_id

        line_collection.insert_one(payload)

    except Exception:
        pass


def handle_car_parking(message: str, roi_id: str, jetson_device_id: str, frame: str):
    try:
        payload = {}
        payload["@timestamp"] = datetime.fromisoformat(
            message["@timestamp"].rstrip("Z")
        )
        payload["event_id"] = message["event"]["id"]
        payload["roi_id"] = int(roi_id)
        payload["jetson_device_id"] = jetson_device_id
        payload["event_type"] = "car_parking"

        threading.Thread(
            target=http_send_report,
            args=(
                payload["event_id"],
                payload["roi_id"],
                payload["@timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                0,
                jetson_device_id,
                frame,
                True,
            ),
        ).start()

        roi_collection.insert_one(payload)

    except Exception:
        traceback.print_exc()


def on_message(channel, method_frame, header_frame, body):
    try:
        # Convert message body to dictionary
        message = json.loads(body)

        elements = message["object"]["person"]["apparel"].split(";")

        if elements[0] == "car-parking":
            handle_car_parking(
                message=message,
                roi_id=elements[1],
                jetson_device_id=elements[2],
                frame=elements[3],
            )
        elif elements[0] == "line-cross":
            handle_line_message(
                message=message, line_id=elements[1], jetson_device_id=elements[2]
            )
        elif elements[0] == "roi":
            if len(elements) == 4:
                handle_roi_message(
                    message=message,
                    roi_id=elements[1],
                    jetson_device_id=elements[2],
                    frame=elements[3],
                )
            else:
                handle_roi_message(
                    message=message,
                    roi_id=elements[1],
                    jetson_device_id=elements[2],
                    frame=None,
                )
        else:
            handle_roi_message(
                message=message,
                roi_id=elements[0],
                jetson_device_id=elements[1],
                frame=None,
            )

    except Exception:
        traceback.print_exc()

    # Acknowledge the message
    channel.basic_ack(delivery_tag=method_frame.delivery_tag)


try:
    # Establish connections
    rabbitmq_conn = connect_to_rabbitmq()
    channel = rabbitmq_conn.channel()
    channel.queue_declare(queue="workspace_analytics", durable=True)
    channel.queue_bind(
        exchange="amq.topic", queue="workspace_analytics", routing_key="*"
    )

    channel.basic_consume(queue="workspace_analytics", on_message_callback=on_message)

    print("Waiting for messages. To exit press CTRL+C")
    channel.start_consuming()

except Exception as e:
    print("Error:", e)
