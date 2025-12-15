# TECHNICAL DESIGN DOCUMENT  
## LiveSense – Real-time Broadcast Quality Assurance Platform

**Version:** 1.0.0  
**Date:** December 15, 2025  
**Type:** Internal Technical Specification  
**Audience:** Project Members / Developers / Data Engineers  

---

## 1. EXECUTIVE SUMMARY

**LiveSense** là một hệ thống **Big Data thời gian thực (Real-time Streaming System)** dùng để:

- Giám sát **chất lượng trải nghiệm (QoE)** của livestream
- Phát hiện **sự cố kỹ thuật** (lag, mất tiếng, delay)
- Quản trị **rủi ro nội dung & độc hại** (toxic chat, spam, backlash)

Hệ thống sử dụng **chat của khán giả làm cảm biến (Human Sensors)**, áp dụng **Deep Learning (NLP)** để phân tích hàng nghìn bình luận mỗi giây và sinh cảnh báo gần như tức thì cho đội vận hành.

---

## 1.1. TECHNICAL GOALS

| Goal | Description |
|----|----|
| **Low Latency** | Thời gian từ lúc comment xuất hiện → cảnh báo < **5 giây** |
| **Scalability** | Xử lý > **2,000 messages/second** trên cụm Docker |
| **Advanced NLP** | Tích hợp Transformer vào Spark Streaming bằng **ONNX + Quantization** |

---

## 2. SYSTEM ARCHITECTURE

Hệ thống được xây dựng theo **Kappa Architecture** (Streaming-first), triển khai hoàn toàn bằng **Docker Containers**.

### 2.1. High-level Flow

1.  **Data Collection**: Scraper thu thập comment từ livestream (YouTube/Twitch) theo thời gian thực.
2.  **Ingestion**: Dữ liệu thô được đẩy vào **Kafka** topic.
3.  **Stream Processing**: **Spark Streaming** đọc dữ liệu từ Kafka:
    *   Tiền xử lý (Clean, Tokenize).
    *   Dự đoán cảm xúc/độc hại bằng **ONNX Model**.
    *   Tính toán các chỉ số (Metrics Aggregation) theo cửa sổ thời gian (Windowing).
4.  **Storage**: Kết quả được lưu vào **PostgreSQL** (metrics) và **Elasticsearch** (logs).
5.  **Serving**: **Streamlit Dashboard** hiển thị biểu đồ và **Alert Engine** gửi cảnh báo qua Telegram nếu vượt ngưỡng.

### 2.2. Component Diagram
graph LR
    User[Livestream Users] -->|Chat| Producer[Chat Producer]
    Producer --> Kafka[Apache Kafka]
    Kafka --> Spark[Spark Structured Streaming]
    subgraph "Spark Processing Core"
        Spark --> Pre[Text Normalization]
        Pre --> Model[ONNX NLP Inference]
        Model --> Agg[Window Aggregation]
    end
    Agg --> DB[(PostgreSQL / Elasticsearch)]
    DB --> UI[Streamlit Dashboard]


## 2.3. TECH STACK

| Layer | Technology | Role |
|------|-----------|------|
| Ingestion | Apache Kafka 3.4 | Message broker, buffer dữ liệu |
| Processing | Apache Spark 3.3 (PySpark) | Streaming engine |
| NLP | PhoBERT / XLM-R + ONNX Runtime | Phân loại comment |
| Storage | PostgreSQL 15 | Lưu metrics & alert history |
| Search (Opt) | Elasticsearch 8.x | Full-text & analytics |
| UI | Streamlit | Dashboard real-time |
| Infra | Docker + Docker Compose | Môi trường triển khai |

---

## 3. DATA PIPELINE

Luồng dữ liệu được thiết kế để đảm bảo tính toàn vẹn và độ trễ thấp (End-to-End Latency < 5s).

### 3.1. Ingestion Layer
- **Source**: YouTube Live Chat, Twitch Chat.
- **Tools**: Custom Scrapers (`ingestion/scraper/`).
- **Message Broker**: Kafka Cluster (2 Brokers).
- **Topic**: `live_chat_raw`.
- **Format**: JSON.
  ```json
  {
    "platform": "youtube",
    "channel_id": "UCxyz...",
    "user": "user123",
    "message": "lag quá admin ơi",
    "timestamp": 1702627200
  }
  ```

### 3.2. Processing Layer (Spark Streaming)
- **Framework**: Apache Spark 3.3 (PySpark).
- **Micro-batch**: 1 second.
- **Tasks**:
    1.  **Preprocessing**: Loại bỏ emoji, link, chuẩn hóa text.
    2.  **Inference**: Sử dụng UDF (User Defined Function) để gọi ONNX Runtime.
    3.  **Aggregation**: Group by `window(timestamp, "1 minute")`.
    4.  **Watermarking**: Xử lý dữ liệu đến muộn (late data) trong 10 giây.

### 3.3. Storage Layer
- **PostgreSQL**: Lưu trữ Time-series metrics (số lượng comment tiêu cực, điểm QoE trung bình).
- **Elasticsearch**: Đánh chỉ mục toàn văn (Full-text search) để tra cứu lịch sử comment.

---

## 4. NLP MODEL

Hệ thống sử dụng mô hình ngôn ngữ nhỏ gọn nhưng hiệu quả để phân loại bình luận.

### 4.1. Model Architecture
- **Base Model**: `vinai/phobert-base` hoặc `xlm-roberta-base`.
- **Task**: Sentiment Analysis / Toxicity Detection.
- **Labels**:
    - `0`: Positive/Neutral (Bình thường).
    - `1`: Negative/Complaint (Phàn nàn về chất lượng: lag, mờ, mất tiếng).
    - `2`: Toxic/Spam (Chửi bới, spam).

### 4.2. Optimization (ONNX)
Để đạt tốc độ xử lý cao trên CPU, mô hình được tối ưu hóa:
- **Format**: Chuyển đổi từ PyTorch (`.pt`) sang ONNX (`.onnx`).
- **Quantization**: Dynamic Quantization (INT8) giảm kích thước model 4x và tăng tốc độ inference 2-3x.
- **Inference Engine**: ONNX Runtime.

### 4.3. Performance
- **Latency**: ~5ms/sample (trên CPU thông thường).
- **Accuracy**: > 85% trên tập dữ liệu test.
