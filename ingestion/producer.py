import json
import sys
import logging
import argparse
import os
from typing import Dict, Any
from kafka import KafkaProducer
from kafka.errors import KafkaError
from scraper.youtube import YouTubeLiveChatScraper

# --- Cấu hình Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MainProducer")

class BaseKafkaProducer:
    """
    Base class chịu trách nhiệm kết nối và gửi dữ liệu thô tới Kafka.
    """
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self._producer = None
        self._connect()

    def _connect(self):
        """Thiết lập kết nối tới Kafka Broker."""
        try:
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',             # Đợi tất cả replica xác nhận
                retries=5,              # Thử lại nếu lỗi mạng
                request_timeout_ms=20000
            )
            logger.info(f"✅ Connected to Kafka at {self.bootstrap_servers}")
        except Exception as e:
            logger.critical(f"❌ Failed to connect to Kafka: {e}")
            sys.exit(1)

    def send_message(self, topic: str, data: Dict[str, Any]):
        """Gửi message tới một topic cụ thể với callback."""
        try:
            future = self._producer.send(topic, value=data)
            # Asynchronous callback
            future.add_callback(self._on_send_success)
            future.add_errback(self._on_send_error)
        except Exception as e:
            logger.error(f"Error calling send(): {e}")

    def _on_send_success(self, record_metadata):
        """Callback khi gửi thành công."""
        logger.debug(f"Sent to {record_metadata.topic} [{record_metadata.partition}] offset {record_metadata.offset}")

    def _on_send_error(self, excp):
        """Callback khi gửi thất bại."""
        logger.error(f"❌ Kafka Send Error: {excp}")

    def close(self):
        """Đóng kết nối an toàn."""
        if self._producer:
            self._producer.flush()
            self._producer.close()
            logger.info("Kafka Producer closed.")

class YouTubeChatProducer(BaseKafkaProducer):
    """
    Class Producer chuyên dụng cho YouTube Chat.
    """
    def __init__(self, bootstrap_servers: str, topic: str, scraper: YouTubeLiveChatScraper, video_id: str):
        super().__init__(bootstrap_servers) 
        self.topic = topic
        self.scraper = scraper
        self.video_id = video_id

    def start_streaming(self):
        """Bắt đầu lắng nghe Scraper và đẩy dữ liệu sang Kafka."""
        logger.info(f"🚀 Starting producer pipeline for Video: {self.video_id} -> Topic: {self.topic}")
        
        count = 0
        try:
            # scraper.stream_live_comments là một Generator , Nó sẽ tự động sleep và wake up khi có data mới
            for msg in self.scraper.stream_live_comments(self.video_id):
                
                # Gửi message vào Kafka
                self.send_message(self.topic, msg)
                
                count += 1
                if count % 10 == 0:
                    logger.info(f"Processed {count} messages so far...")

        except KeyboardInterrupt:
            logger.warning("🛑 Streaming stopped by user.")
        except Exception as e:
            logger.error(f"🔥 Unexpected error in streaming loop: {e}")
        finally:
            self.close()

# --- Hàm hỗ trợ ---
def parse_args():
    parser = argparse.ArgumentParser(description="Kafka YouTube Chat Producer")
    
    parser.add_argument('--video_id', type=str, required=True, 
                        help='YouTube Video ID (e.g., jfKfPfyJRdk)')
    parser.add_argument('--topic', type=str, default='youtube_live_chat', 
                        help='Kafka topic name (default: youtube_live_chat)')
    parser.add_argument('--server', type=str, default='localhost:9092', 
                        help='Kafka bootstrap servers (default: localhost:9092)')
    
    return parser.parse_args()

# --- Main Execution ---
if __name__ == "__main__":
    # 1. Lấy tham số
    args = parse_args()
    
    # 2. Lấy API Key
    API_KEY = os.getenv("YOUTUBE_API_KEY")
    if not API_KEY:
        logger.critical("❌ Error: Missing Environment Variable YOUTUBE_API_KEY")
        sys.exit(1)

    # 3. Khởi tạo Scraper
    try:
        scraper_instance = YouTubeLiveChatScraper(API_KEY)
    except Exception as e:
        logger.critical(f"❌ Could not initialize Scraper: {e}")
        sys.exit(1)

    # 4. Khởi tạo Producer và chạy
    producer_service = YouTubeChatProducer(
        bootstrap_servers=args.server,
        topic=args.topic,
        scraper=scraper_instance,
        video_id=args.video_id
    )

    producer_service.start_streaming()

# run : python producer.py --video_id VIDEO_ID --topic youtube_live_chat 
# notice : VIDEO_ID (must active streaming video)