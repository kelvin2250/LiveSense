import os
import logging
import praw
from datetime import datetime
from typing import List, Dict, Any, Optional
from praw.models import MoreComments

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RedditCommentScraper:
    """
    Class chịu trách nhiệm lấy bình luận từ một bài post Reddit (Submission).
    Sử dụng thư viện PRAW.
    """

    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        """
        Khởi tạo kết nối tới Reddit API.

        Args:
            client_id (str): ID ứng dụng từ Reddit Apps.
            client_secret (str): Secret key từ Reddit Apps.
            user_agent (str): Chuỗi định danh bot (VD: "my_scraper_bot/1.0").
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self._reddit_client = None

        self._setup_client()

    def _setup_client(self):
        """Thiết lập instance PRAW Reddit."""
        try:
            self._reddit_client = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            # Kiểm tra kết nối bằng cách lấy thông tin user hiện tại (read-only mode vẫn chạy ok)
            logger.info(f"Reddit API client initialized with User Agent: {self.user_agent}")
        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {e}")
            raise

    def fetch_comments(self, post_url: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Lấy bình luận từ một URL bài viết Reddit.

        Args:
            post_url (str): Link đầy đủ của bài post.
            limit (int): Giới hạn số lượng comment muốn lấy (tính cả comment con).

        Returns:
            List[Dict]: Danh sách các comment đã chuẩn hóa.
            Cấu trúc đồng bộ với YouTube Scraper:
            [
                {
                    "id": "k1m...",
                    "post_id": "18a...",    # Tương đương video_id
                    "author": "username",
                    "text": "Nội dung...",
                    "like_count": 150,      # Reddit gọi là Score (Up - Down)
                    "published_at": "2023-...",
                    "source": "reddit"
                }, ...
            ]
        """
        comments_data = []
        try:
            # Tạo object Submission từ URL
            submission = self._reddit_client.submission(url=post_url)
            
            # Logic xử lý "MoreComments":
            # Reddit trả về cấu trúc cây. replace_more(limit=0) sẽ loại bỏ các nút "Load more comments"
            # và làm phẳng danh sách comment hiện có để dễ xử lý.
            # Nếu muốn lấy TẤT CẢ comment (cẩn thận rate limit), tăng limit lên.
            submission.comments.replace_more(limit=0) 
            
            # Lấy toàn bộ comment (đã được làm phẳng)
            all_comments = submission.comments.list()

            # Cắt danh sách theo limit yêu cầu
            for comment in all_comments[:limit]:
                parsed = self._parse_comment_data(comment, submission.id)
                if parsed:
                    comments_data.append(parsed)

            logger.info(f"Successfully fetched {len(comments_data)} comments from Reddit post {submission.id}.")
            return comments_data

        except Exception as e:
            logger.error(f"Error fetching comments from {post_url}: {e}")
            return []

    def _parse_comment_data(self, comment, post_id: str) -> Optional[Dict[str, Any]]:
        """
        Chuyển đổi object PRAW Comment thành dictionary chuẩn.
        """
        try:
            # Xử lý trường hợp tác giả đã xóa tài khoản (author là None)
            author_name = comment.author.name if comment.author else "[deleted]"
            
            # Chuyển timestamp Unix sang ISO format
            created_dt = datetime.fromtimestamp(comment.created_utc)
            
            return {
                "id": comment.id,
                "post_id": post_id, # Dùng chung key logic với video_id của youtube hoặc đặt tên chung là content_id
                "author": author_name,
                "text": comment.body,
                "like_count": comment.score, # Score = Upvotes - Downvotes
                "published_at": created_dt.isoformat(),
                "source": "reddit"
            }
        except Exception as e:
            logger.warning(f"Error parsing comment {comment.id}: {e}")
            return None

# --- Khối chạy thử nghiệm ---
if __name__ == "__main__":
    # Cần tạo App tại https://www.reddit.com/prefs/apps để lấy ID/Secret
    # Chọn loại app là "Script"
    CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
    CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
    USER_AGENT = "python:comment_scraper:v1.0 (by /u/YourUsername)"

    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Lỗi: Thiếu biến môi trường REDDIT_CLIENT_ID hoặc REDDIT_CLIENT_SECRET")
    else:
        scraper = RedditCommentScraper(CLIENT_ID, CLIENT_SECRET, USER_AGENT)
        
        # Test với một bài post thực tế
        TEST_URL = "https://www.reddit.com/r/Python/comments/18kz4j6/what_is_the_best_way_to_learn_python/"
        
        print(f"🔄 Đang lấy bình luận từ: {TEST_URL}...")
        results = scraper.fetch_comments(post_url=TEST_URL, limit=5)
        
        print("\n✅ Kết quả mẫu:")
        for c in results:
            print(c)