import yt_dlp
import pandas as pd
import json
import os

# Configuration
VIDEO_URL = 'https://www.youtube.com/watch?v=QP_XewZa1sU'
OUTPUT_JSON = 'youtube_chat_temp.json' 
OUTPUT_CSV = 'live_chat_1000.csv'      
LIMIT_MSG = 1000                      

def download_chat_raw(video_url):
    print(f"[Bước 1] Đang tải dữ liệu chat thô từ YouTube...")
    print(" (Việc này mất khoảng 1-2 phút tùy mạng, vui lòng chờ...)")
    
    # Cấu hình yt-dlp
    ydl_opts = {
        'skip_download': True,       
        'writesubtitles': True,      # Lấy sub (chat)
        'subtitleslangs': ['live_chat'], 
        'outtmpl': OUTPUT_JSON,     
        'quiet': True,               
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        print("[Bước 1] Tải xong dữ liệu thô!")
        return True
    except Exception as e:
        print(f"Lỗi tải: {e}")
        return False

def process_json_to_csv_limited():
    print(f"[Bước 2] Đang lọc lấy {LIMIT_MSG} bình luận đầu tiên...")
    
    # Tìm file json vừa tải (vì yt-dlp hay tự đổi tên file)
    target_file = None
    for f in os.listdir():
        if f.startswith(OUTPUT_JSON) and f.endswith('.json'):
            target_file = f
            break
            
    if not target_file:
        print("Không tìm thấy file JSON.")
        return

    chats = []
    
    # Đọc file và lọc
    with open(target_file, 'r', encoding='utf-8') as f:
        for line in f:
            # Kiểm tra giới hạn TRƯỚC khi xử lý
            if len(chats) >= LIMIT_MSG:
                print(f"Đã đủ {LIMIT_MSG} tin nhắn. Dừng xử lý!")
                break

            try:
                item = json.loads(line)
                
                # Logic trích xuất dữ liệu của yt-dlp
                actions = item.get('replayChatItemAction', {}).get('actions', [])
                for action in actions:
                    if 'addChatItemAction' in action:
                        details = action['addChatItemAction']['item'].get('liveChatTextMessageRenderer')
                        if details:
                            # Lấy nội dung
                            msg_runs = details.get('message', {}).get('runs', [])
                            message = "".join([r.get('text', '') for r in msg_runs])
                            author = details.get('authorName', {}).get('simpleText', 'Unknown')
                            timestamp = details.get('timestampText', {}).get('simpleText', '')
                            
                            chats.append({
                                'author': author,
                                'message': message,
                                'timestamp': timestamp
                            })
                        
                            if len(chats) >= LIMIT_MSG:
                                break
                                
            except Exception:
                continue

    # Lưu ra CSV
    if chats:
        df = pd.DataFrame(chats)
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        print(f"\n HOÀN TẤT! File kết quả: {OUTPUT_CSV}")
        print(f"Dữ liệu mẫu ({len(df)} dòng):")
        print(df.head())
        
        try:
            os.remove(target_file)
            print("Đã dọn dẹp file tạm.")
        except:
            pass
    else:
        print("Không lấy được tin nhắn nào.")

if __name__ == "__main__":
    if download_chat_raw(VIDEO_URL):
        process_json_to_csv_limited()