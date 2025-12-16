import os
import logging
from typing import List, Dict, Optional, Any , Generator
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import argparse
import sys 
from dotenv import load_dotenv
import time 
import json 


load_dotenv()

# Cấu hình logging chuẩn
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


class YouTubeLiveChatScraper:
    """
    Class chịu trách nhiệm lấy bình luận từ YouTube Video hoặc Archived Stream.
    Sử dụng YouTube Data API v3.
    """

    def __init__(self, api_key: str):
        """
        Khởi tạo Scraper với API Key.

        Args:
            api_key (str): Key lấy từ Google Cloud Console.
        """
        self.api_key = api_key
        self.service_name = "youtube"
        self.api_version = "v3"
        self._youtube_client = None

        self._setup_client()

    def _setup_client(self):
        """Thiết lập kết nối tới YouTube API."""
        try:
            self._youtube_client = build(
                self.service_name, 
                self.api_version, 
                developerKey=self.api_key
            )
            logger.info("YouTube API client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize YouTube client: {e}")
            raise

    def get_active_live_chat_id(self, video_id: str) -> Optional[str]:
        """
        Lấy activeLiveChatId từ video_id.
        Đây là ID bắt buộc để gọi API liveChatMessages.
        """
        try:
            response = self._youtube_client.videos().list(
                part="liveStreamingDetails",
                id=video_id
            ).execute()

            items = response.get("items", [])
            if not items:
                logger.error(f"Video {video_id} not found.")
                return None

            live_details = items[0].get("liveStreamingDetails", {})
            chat_id = live_details.get("activeLiveChatId")
        
            if not chat_id:
                logger.warning(f"Video {video_id} is not live or does not have an active chat.")
                return None
            
            logger.info(f"Found Active Chat ID: {chat_id}")
            return chat_id

        except HttpError as e:
            logger.error(f"Error getting live chat ID: {e}")
            return None

    def stream_live_comments(self, video_id: str) -> Generator[Dict[str, Any], None, None]:
        """
        Hàm Generator lắng nghe và trả về comment theo thời gian thực.
        Thay vì return 1 list, hàm này sẽ 'yield' từng comment ngay khi lấy được.
        
        """
        live_chat_id = self.get_active_live_chat_id(video_id)
        if not live_chat_id:
            return

        next_page_token = None
        
        logger.info(f"Starting to poll live chat for video {video_id}...")

        while True:
            try:
                # Gọi API lấy tin nhắn
                request = self._youtube_client.liveChatMessages().list(
                    liveChatId=live_chat_id,
                    part="snippet,authorDetails",
                    pageToken=next_page_token
                )
                response = request.execute()

                # 1. Xử lý các tin nhắn trong batch này
                items = response.get("items", [])
                for item in items:
                    parsed_item = self._parse_live_message(item, video_id)
                    if parsed_item:
                        yield parsed_item # tra cho producer 

                # 2. Lấy token cho trang tiếp theo
                next_page_token = response.get("nextPageToken")

                # 3. Quan trọng: Ngủ đúng thời gian quy định của YouTube
                polling_interval = response.get("pollingIntervalMillis", 3000) / 1000
                
                # Logic an toàn: Nếu stream kết thúc (offlineAt), API có thể trả về list rỗng và interval lớn
                live_details = response.get("pageInfo", {})
                if not items and not next_page_token:
                    logger.info("Stream ended or no more messages.")
                    break

                logger.debug(f"Sleeping for {polling_interval} seconds...")
                time.sleep(polling_interval)

            except HttpError as e:
                logger.error(f"HTTP Error during polling: {e}")
                time.sleep(5) 
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break

    def _parse_live_message(self, item: Dict, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Parse dữ liệu Live Chat Message (cấu trúc khác với Comment tĩnh).
        """
        try:
            snippet = item["snippet"]
            author_details = item["authorDetails"]

            # Nội dung tin nhắn nằm trong 'displayMessage' hoặc 'textMessageDetails'
            text_content = snippet.get("displayMessage")
            
            # Bỏ qua các tin nhắn hệ thống (VD: User A became a member) nếu không có text
            if not text_content:
                return None

            return {
                "id": item["id"],
                "video_id": video_id,
                "author": author_details.get("displayName", "Unknown"),
                "text": text_content,
                "published_at": snippet.get("publishedAt"),
                "source": "youtube_live", 
                "is_chat_owner": author_details.get("isChatOwner", False),
                "is_chat_moderator": author_details.get("isChatModerator", False)
            }
        except KeyError as e:
            logger.warning(f"Error parsing live message: {e}")
            return None

def get_args():
    parser = argparse.ArgumentParser(
        description="Args streaming video youtube"
    )
    parser.add_argument(
        "--video_id",
        help="YouTube video ID"
    )
    return parser.parse_args()

if __name__ == "__main__":
    API_KEY = os.getenv("YOUTUBE_API_KEY")
    args = get_args()
    TEST_VIDEO_ID = args.video_id


    if not API_KEY:
        print("❌ Missing API Key")
    
    else:
        scraper = YouTubeLiveChatScraper(API_KEY)
        
        print(f"📡 Đang kết nối tới Live Stream: {TEST_VIDEO_ID}")
        
        # Dùng vòng lặp để hứng dữ liệu realtime
        try:
            for msg in scraper.stream_live_comments(TEST_VIDEO_ID):
                print(f"[{msg['published_at']}] {msg['author']}: {msg['text']}")
        except KeyboardInterrupt:
            print("\n🛑 Đã dừng scraper.")

# run test : python youtube.py --video_id VIDEO_ID (must active streaming video)

# py youtube.py --video_id 