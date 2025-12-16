CREATE TABLE IF NOT EXISTS live_chat_sentiment (
    id VARCHAR(255) PRIMARY KEY,
    video_id VARCHAR(50),
    published_at TIMESTAMP,
    author TEXT,
    content  TEXT,
    sentiment_score FLOAT,    -- Điểm số cảm xúc (-1 đến 1)
    sentiment_label VARCHAR(20), -- POSITIVE, NEUTRAL, NEGATIVE
    source VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tạo index để query nhanh theo video hoặc thời gian   
CREATE INDEX idx_video_id ON live_chat_sentiment(video_id);
CREATE INDEX idx_timestamp ON live_chat_sentiment(published_at);