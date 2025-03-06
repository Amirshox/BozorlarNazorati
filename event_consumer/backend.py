
from fastapi import FastAPI, HTTPException, status, Depends, BackgroundTasks
import pika, os, json
from datetime import datetime
from database import  get_collection

from routers import roi_analytics
import threading
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

app = FastAPI()

collection = get_collection()

# RabbitMQ connection details
RABBIT_MQ_HOST = os.getenv("RABBIT_MQ_HOST")
RABBIT_MQ_PORT = int(os.getenv("RABBIT_MQ_PORT"))
RABBIT_MQ_USERNAME = os.getenv("RABBIT_MQ_USER")
RABBIT_MQ_PASSWORD = os.getenv("RABBIT_MQ_PASSWORD")

def connect_to_rabbitmq():
    credentials = pika.PlainCredentials(RABBIT_MQ_USERNAME, RABBIT_MQ_PASSWORD)
    parameters = pika.ConnectionParameters(host=RABBIT_MQ_HOST, port=RABBIT_MQ_PORT, credentials=credentials)
    return pika.BlockingConnection(parameters)

def on_message(channel, method_frame, header_frame, body):
    try:
        message = json.loads(body)
        
        roi_id, roi_points, jetson_device_id = message["object"]["person"]["apparel"].split(";")

        payload = {
            "@timestamp": datetime.fromisoformat(message["@timestamp"].rstrip("Z")),
            "event_type": "entrance" if message["event"]["type"] == "parked" else "exit",
            "event_id": message["event"]["id"],
            "roi_id": roi_id,
            "roi_points": roi_points,
            "jetson_device_id": jetson_device_id,
            "number_of_people": message["object"]["person"]["age"]
        }

        collection.insert_one(payload)
        print("Message stored in MongoDB:", payload)
    except Exception as e:
        print("Error processing message:", e)
    channel.basic_ack(delivery_tag=method_frame.delivery_tag)

def consume_messages():
    connection = connect_to_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue='workspace_analytics')
    channel.queue_bind(exchange="amq.topic", queue="workspace_analytics", routing_key="*")
    channel.basic_consume(queue='workspace_analytics', on_message_callback=on_message)
    print('Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

def start_consumer():
    thread = threading.Thread(target=consume_messages)
    thread.start()
@app.on_event("startup")
async def startup_event():
    start_consumer()


app.include_router(roi_analytics.router)