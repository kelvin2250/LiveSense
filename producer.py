import json
import pandas as pd
import time
import os
from datetime import datetime
from kafka import KafkaProducer 

# 1. Cấu hình
# hạy trong Docker (có biến môi trường KAFKA_BROKER), dùng kafka:29092
kafka_broker = os.getenv("KAFKA_BROKER", "localhost:9092")
print(f"Connecting to Kafka at: {kafka_broker}")

producer = KafkaProducer(
    bootstrap_servers=kafka_broker,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def on_send_success(record_metadata):
    print(f"Message delivered to {record_metadata.topic} [{record_metadata.partition}]")

def on_send_error(excp):
    print(f"Message delivery failed: {excp}")

# 2. Đọc dữ liệu
data_stream = pd.read_csv('data/emulator/laibang.csv')

print(f"Starting Stream Emulator...")

for index, row in data_stream.iterrows():
    # Tạo payload đầy đủ để Spark xử lý
    msg = {
        "id": int(index),
        "author": row['author'],
        "message": row['message'],
        # Gán timestamp hiện tại để Spark chạy Windowing chính xác
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "platform": "youtube"
    }
    
    # Gửi message
    future = producer.send("live_chat_laibang", value=msg)
    future.add_callback(on_send_success)
    future.add_errback(on_send_error)
    
    print(f"Sending: {row['author']} - {row['message']}")
    time.sleep(1.0) 

producer.flush()
print("All messages have been sent.")