import os
import logging
import time
import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Generator
from urllib.parse import urlparse, parse_qs

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

# Logger configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("YouTubeScraper")

class YouTubeLiveChatScraper:
    """Scrapes live chat messages from YouTube using Data API v3."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.youtube = build("youtube", "v3", developerKey=self.api_key)
        logger.info("YouTube API client initialized.")

    @staticmethod
    def normalize_video_id(video_input: str) -> str:
        """Extracts Video ID from various URL formats or returns raw ID."""
        if not video_input or "/" not in video_input:
            return video_input.strip()

        parsed = urlparse(video_input.strip())
        if "youtube.com" in parsed.netloc:
            query = parse_qs(parsed.query)
            if "v" in query:
                return query["v"][0]
            # Handle /live/ or /shorts/
            parts = parsed.path.split("/")
            if len(parts) >= 3 and parts[1] in ["live", "shorts"]:
                return parts[2]
        elif "youtu.be" in parsed.netloc:
            return parsed.path.lstrip("/")
        
        return video_input

    def get_chat_id(self, video_id: str) -> Optional[str]:
        """Retrieves the activeLiveChatId for a given video ID."""
        try:
            response = self.youtube.videos().list(
                part="liveStreamingDetails",
                id=video_id
            ).execute()

            items = response.get("items", [])
            if not items:
                logger.error(f"Video {video_id} not found.")
                return None

            chat_id = items[0].get("liveStreamingDetails", {}).get("activeLiveChatId")
            if not chat_id:
                logger.warning(f"No active live chat found for video {video_id}.")
                return None

            return chat_id
        except HttpError as e:
            logger.error(f"API Error: {e}")
            return None

    def stream_live_comments(self, video_id: str) -> Generator[Dict[str, Any], None, None]:
        """Polls live chat and yields parsed messages."""
        chat_id = self.get_chat_id(video_id)
        if not chat_id:
            return

        next_token = None
        while True:
            try:
                request = self.youtube.liveChatMessages().list(
                    liveChatId=chat_id,
                    part="snippet,authorDetails",
                    pageToken=next_token
                )
                response = request.execute()

                # Process messages
                for item in response.get("items", []):
                    parsed = self._parse_message(item, video_id)
                    if parsed:
                        yield parsed

                next_token = response.get("nextPageToken")
                if not next_token:
                    logger.info("Chat stream ended.")
                    break

                # Respect YouTube's suggested polling interval
                wait_ms = response.get("pollingIntervalMillis", 3000)
                time.sleep(wait_ms / 1000)

            except HttpError as e:
                logger.error(f"Polling error: {e}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break

    def _parse_message(self, item: Dict, video_id: str) -> Optional[Dict[str, Any]]:
        """Extracts relevant fields from raw API item."""
        try:
            return {
                "message_id": item["id"],
                "video_id": video_id,
                "author": item["authorDetails"].get("displayName"),
                "message": item["snippet"].get("displayMessage"),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "platform": "youtube"
            }
        except KeyError:
            return None