import os
import json
import sys
import logging
import argparse
from typing import Dict, Any
from kafka import KafkaProducer
from scraper.youtube import YouTubeLiveChatScraper

# Logger configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("KafkaProducer")

class BaseKafkaProducer:
    """Handles Kafka connection and core sending logic."""
    def __init__(self, bootstrap_servers: str):
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=5
            )
            logger.info(f"Connected to Kafka: {bootstrap_servers}")
        except Exception as e:
            logger.critical(f"Kafka connection failed: {e}")
            sys.exit(1)

    def send(self, topic: str, data: Dict[str, Any]):
        """Asynchronous send with callbacks."""
        try:
            future = self.producer.send(topic, value=data)
            future.add_callback(lambda meta: logger.debug(f"Sent to {meta.topic} offset {meta.offset}"))
            future.add_errback(lambda e: logger.error(f"Send failed: {e}"))
        except Exception as e:
            logger.error(f"Producer send error: {e}")

    def close(self):
        if self.producer:
            self.producer.flush()
            self.producer.close()

class YouTubeChatProducer(BaseKafkaProducer):
    """Orchestrates scraping and producing to Kafka."""
    def __init__(self, bootstrap_servers: str, topic: str, scraper: YouTubeLiveChatScraper, video_id: str):
        super().__init__(bootstrap_servers)
        self.topic = topic
        self.scraper = scraper
        self.video_id = video_id

    def run(self):
        logger.info(f"Starting stream: Video[{self.video_id}] -> Topic[{self.topic}]")
        try:
            for msg in self.scraper.stream_live_comments(self.video_id):
                self.send(self.topic, msg)
                print(f"Produced: {msg['author']}: {msg['message'][:30]}...")
        except KeyboardInterrupt:
            logger.info("Stopped by user.")
        finally:
            self.close()

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--video_id', required=True, help='YouTube URL or ID')
    parser.add_argument('--topic', default='youtube_live_chat')
    parser.add_argument('--server', default='localhost:9092')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:
        logger.error("Missing YOUTUBE_API_KEY in .env")
        sys.exit(1)

    # Initialize scraper and resolve ID
    scraper = YouTubeLiveChatScraper(api_key)
    target_id = scraper.normalize_video_id(args.video_id)

    # Initialize and run producer
    producer_service = YouTubeChatProducer(
        bootstrap_servers=args.server,
        topic=args.topic,
        scraper=scraper,
        video_id=target_id
    )
    producer_service.run()