# ⚡ LiveSense QoE: Real-time Livestream Analytics & AI Moderation System

> **"Turning Chaos into Insights"** - Hệ thống phân tích thời gian thực giúp Streamer và Moderator thấu hiểu khán giả, phát hiện toxic và nắm bắt khoảnh khắc viral ngay lập tức.

---

## 📖 1. Tổng quan dự án (Project Overview)

**LiveSense QoE** (Quality of Experience) là một giải pháp MLOps toàn diện được thiết kế để giải quyết bài toán quá tải thông tin trong các buổi livestream quy mô lớn. Thay vì để Streamer bị "trôi chat" hoặc Moderator phải căng mắt đọc từng dòng tin nhắn, hệ thống tự động thu thập, phân tích và chuyển đổi hàng ngàn tin nhắn mỗi giây thành các **Tín hiệu vận hành (Operational Signals)** trực quan.

### 🎯 Mục tiêu cốt lõi:
1.  **Real-time Monitoring:** Cung cấp Dashboard thời gian thực với độ trễ thấp (< 5s).
2.  **AI-Powered Moderation:** Tự động phát hiện và cảnh báo các cuộc tấn công ngôn từ (Toxic Attack).
3.  **Engagement Tracking:** Nhận diện khoảnh khắc "đỉnh cao" (Viral Moments) để hỗ trợ đội ngũ Editor.
4.  **Historical Analysis:** Lưu trữ dữ liệu dài hạn để phân tích xu hướng khán giả theo thời gian.

---

## 🏗️ 2. Kiến trúc hệ thống (System Architecture)

Hệ thống được xây dựng theo mô hình **Lambda Architecture** thu nhỏ, đảm bảo cả tốc độ xử lý thời gian thực và khả năng lưu trữ lâu dài.

```mermaid
graph LR
    A[Data Emulator] -->|Producer| B(Kafka Broker)
    B -->|Subscribe| C{Spark Streaming}
    
    subgraph "Processing Core (Docker)"
    C -->|Mock AI Labeling| C
    C -->|Calculate Signals| C
    end
    
    C -->|Hot Path (Real-time)| D[(Redis)]
    C -->|Cold Path (History)| E[(PostgreSQL)]
    
    D -->|Fetch < 1s| F[Streamlit Dashboard]
    E -->|Query| G[Metabase Analytics]
```

### 🛠️ Tech Stack:
*   **Ingestion:** Apache Kafka (KRaft mode) - Message Broker chịu tải cao.
*   **Processing:** Apache Spark Structured Streaming (Pyspark) - Xử lý luồng dữ liệu phân tán.
*   **Storage (Hot):** Redis - In-memory database cho Dashboard thời gian thực.
*   **Storage (Cold):** PostgreSQL - Relational database cho phân tích lịch sử.
*   **Visualization:**
    *   **Streamlit:** Real-time Operational Dashboard.
    *   **Metabase:** Business Intelligence (BI) & Deep Analytics.
*   **Infrastructure:** Docker & Docker Compose.

---

## 📊 3. Hệ thống tín hiệu (The 6 Operational Signals)

Đây là "trái tim" của LiveSense, giúp định lượng cảm xúc và hành vi khán giả thành các con số biết nói.

| Signal | Tên gọi | Ý nghĩa & Ứng dụng | Công thức (Demo) |
| :--- | :--- | :--- | :--- |
| **S1** | **Chat Load** | **"Nhịp tim của Stream"**. Đo lường tốc độ tin nhắn đổ về. Giúp nhận biết độ "nóng" tổng quan của buổi live. | `Total_Msg / 60s` |
| **S2** | **Tech Health** | **"Bác sĩ kỹ thuật"**. Phát hiện khi người xem phàn nàn về lag, mất tiếng, drop frame. | `% Technical_Issue` |
| **S3** | **Demand Pressure** | **"Áp lực yêu cầu"**. Đo lường mức độ đòi hỏi của khán giả (yêu cầu chơi game khác, đổi nhạc...). | `Request_Count / 60s` |
| **S4** | **Backseat Pressure** | **"Chỉ số dạy đời"**. Đo lường mức độ khán giả chỉ trích hoặc chỉ đạo cách chơi game (Backseating). | `% Performance_Feedback` |
| **S5** | **Toxic Pressure** | **"Hệ thống an ninh"**. Cảnh báo ĐỎ khi xuất hiện làn sóng tấn công, chửi bới, xúc phạm. | `Toxic_Count / 60s` |
| **S6** | **Engagement Heat** | **"Máy dò Highlight"**. Nhận diện khoảnh khắc bùng nổ cảm xúc (Viral), hỗ trợ cắt clip highlight tự động. | `Excitement_Count / 60s` |

---

## 🚀 4. Hướng dẫn cài đặt & Chạy (Installation & Usage)

### Yêu cầu tiên quyết (Prerequisites):
*   Docker & Docker Compose
*   Python 3.9+
*   Git

### Bước 1: Khởi tạo môi trường hạ tầng
Dựng toàn bộ các services (Spark, Kafka, Redis, Postgres, Metabase) bằng Docker.

```bash
# Tại thư mục gốc dự án
docker-compose up -d
```
*Chờ khoảng 30s - 1 phút để các container khởi động hoàn toàn.*

### Bước 2: Cài đặt thư viện Python (Client Side)
Cài đặt các thư viện cần thiết để chạy Producer và Dashboard ở máy local.

```bash
pip install kafka-python pandas streamlit redis
```

### Bước 3: Kích hoạt hệ thống (Theo thứ tự)

**1. Khởi chạy Spark Consumer (Bộ não xử lý):**
Consumer sẽ lắng nghe Kafka, xử lý dữ liệu và đẩy vào Redis/Postgres.
```bash
docker exec -it spark-master python3 /app/consumer.py
```

**2. Khởi chạy Streamlit Dashboard (Màn hình theo dõi):**
Mở một terminal mới:
```bash
streamlit run dashboard.py
```
*Truy cập: http://localhost:8501*

**3. Bắt đầu giả lập dữ liệu (Data Generator):**
Mở một terminal mới để bắn dữ liệu giả lập vào hệ thống:
```bash
python producer.py
```

---

## 📈 5. Phân tích sâu với Metabase (Deep Analytics)

Sau khi hệ thống chạy xong, dữ liệu lịch sử được lưu tại PostgreSQL. Bạn có thể dùng Metabase để trả lời các câu hỏi vĩ mô:

1.  Truy cập: `http://localhost:3000`
2.  Setup tài khoản Admin (lần đầu).
3.  Kết nối Database:
    *   **Host:** `postgres`
    *   **DB Name:** `metabaseappdb`
    *   **User:** `phat` / **Pass:** `123456`
4.  **Gợi ý biểu đồ:**
    *   *Line Chart:* Xu hướng Toxic (S5) trong suốt 2 tiếng livestream.
    *   *Pie Chart:* Tỉ lệ cảm xúc khán giả (Vui vẻ vs. Giận dữ).
    *   *Table:* Danh sách top những user có hành vi toxic nhất.

---

## 📂 6. Cấu trúc dự án (Project Structure)

```
LiveSense-QoE/
├── data/                   # Dữ liệu giả lập (CSV)
│   └── emulator/
│       └── laibang.csv     # Log chat mẫu
├── consumer.py             # [Core] Spark Streaming logic, AI simulation, Sink to Redis/DB
├── producer.py             # [Source] Giả lập gửi tin nhắn vào Kafka
├── dashboard.py            # [UI] Streamlit Dashboard hiển thị Real-time
├── docker-compose.yml      # [Infra] Định nghĩa toàn bộ hạ tầng Docker
├── Dockerfile.spark        # [Infra] Custom Image cho Spark (cài thêm thư viện)
└── README.md               # Tài liệu dự án
```

---

## 🔮 7. Định hướng phát triển (Future Roadmap)

*   **Phase 1 (Hiện tại):** Hoàn thiện luồng dữ liệu (Pipeline) và Dashboard cơ bản với Mock AI.
*   **Phase 2:** Tích hợp **Model AI thật** (BERT/RoBERTa) để thay thế module random hiện tại.
*   **Phase 3:** Xây dựng tính năng **Auto-Mod** (Tự động ẩn comment toxic trên nền tảng stream thông qua API).
*   **Phase 4:** Triển khai lên Cloud (AWS/GCP) với Kubernetes để chịu tải hàng triệu users.

---
*Project by [Your Name] - MLOps Course Final Project*
