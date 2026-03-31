# 🚀 LiveSense QoE - Quick Start Guide

**Hướng dẫn chạy project từ A-Z trên Windows**

---

## 📋 Kiểm tra Điều kiện Tiên quyết

Mở **PowerShell** và chạy những lệnh này để kiểm tra:

```powershell
# 1. Kiểm tra Docker
docker --version
docker-compose --version

# 2. Kiểm tra Python
python --version
# Nên có Python 3.9+

# 3. Kiểm tra Git
git --version

# 4. Kiểm tra xem Docker Desktop đã chạy chưa
docker ps
```

Nếu tất cả OK → tiếp tục bước tiếp theo.

---

## 🔧 BƯỚC 1: Xây dựng Docker Images (Chỉ làm 1 lần)

Mở **PowerShell** và chuyển đến thư mục project:

```powershell
# Di chuyển vào project
cd d:\SubjectSchool\MLops\LiveSense-QoE

# Xây dựng custom Spark image
docker build -f Dockerfile.spark -t spark-custom .

# Chờ ~5-10 phút cho quá trình build xong
# Sẽ thấy: "Successfully tagged spark-custom:latest"
```

---

## 🐳 BƯỚC 2: Khởi động Docker Services

```powershell
# Vẫn ở thư mục d:\SubjectSchool\MLops\LiveSense-QoE

# Khởi động tất cả services (Kafka, Spark, Postgres, Redis, Metabase)
docker-compose up -d

# Chờ ~1-2 phút cho tất cả container khởi động
# Kiểm tra status
docker-compose ps
```

**Sau khi chạy `docker-compose ps`, bạn sẽ thấy:**
```
NAME               STATUS              PORTS
spark-master       Up (healthy)        0.0.0.0:7077->7077/tcp, 0.0.0.0:8080->8080/tcp
spark-worker       Up (healthy)        0.0.0.0:8081->8081/tcp
kafka              Up (healthy)        0.0.0.0:9092->9092/tcp
postgres           Up (healthy)        0.0.0.0:5432->5432/tcp
redis              Up (healthy)        0.0.0.0:6379->6379/tcp
metabase           Up (healthy)        0.0.0.0:3000->3000/tcp
```

**Kiểm tra các services có hoạt động:**
```powershell
# Kiểm tra Kafka
docker logs kafka | Select-Object -First 20

# Kiểm tra Spark Master
docker logs spark-master | Select-Object -First 20
```

---

## 🐍 BƯỚC 3: Tạo Conda Env và Cài Dependencies

```powershell
# Vẫn ở thư mục project
cd d:\SubjectSchool\MLops\LiveSense-QoE

# Nếu chưa bật conda cho PowerShell (chạy 1 lần duy nhất)
conda init powershell

# Tạo conda environment
conda create -n mlops python=3.10 -y

# Kích hoạt conda environment
conda activate mlops

# Cài đặt dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Kiểm tra cài đặt xong
pip list | Select-String "kafka|redis|pyspark|streamlit|onnxruntime|transformers"
```

---

## ▶️ BƯỚC 4: Chạy Project (3 Terminal)

### **Terminal 1: Producer (Lấy dữ liệu)**

```powershell
# Mở PowerShell terminal mới
cd d:\SubjectSchool\MLops\LiveSense-QoE
conda activate mlops

# Tạo topic trước (chạy 1 lần hoặc khi topic chưa có)
docker exec kafka kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic live_chat_midfeed --partitions 1 --replication-factor 1

# Chạy producer từ YouTube Live Chat (đúng tham số)
python producer.py --video_id YOUR_LIVE_VIDEO_ID --topic live_chat_midfeed --server localhost:9092
```

**Lưu ý:** file emulator hiện tại chỉ tải dữ liệu chat về CSV, chưa đẩy vào Kafka.

---

### **Terminal 2: Consumer (Xử lý dữ liệu với Spark)**

```powershell
# Mở PowerShell terminal mới
cd d:\SubjectSchool\MLops\LiveSense-QoE
conda activate mlops

# Chạy qua Spark trong Docker (khuyên dùng)
docker exec spark-master spark-submit `
  --master spark://spark-master:7077 `
  --deploy-mode client `
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.6.0 `
  /app/consumer.py `
  --kafka-broker kafka:29092 `
  --topic live_chat_midfeed `
  --redis-host redis
```

---

### **Terminal 3: Dashboard (Visualization)**

```powershell
# Mở PowerShell terminal mới
cd d:\SubjectSchool\MLops\LiveSense-QoE
conda activate mlops

# Chạy Streamlit dashboard
streamlit run dashboard.py
```

**Sẽ tự mở browser tại:** `http://localhost:8501`

---

## 📊 BƯỚC 5: Kiểm tra Dữ liệu

Khi tất cả đang chạy, kiểm tra xem dữ liệu có chảy không:

### **Kiểm tra Kafka:**
```powershell
# Xem topics
docker exec kafka kafka-topics --bootstrap-server kafka:9092 --list

# Xem messages trong topic
docker exec kafka kafka-console-consumer --bootstrap-server kafka:9092 --topic live_chat_midfeed --from-beginning --max-messages 10
```

### **Kiểm tra Redis:**
```powershell
# Kết nối Redis CLI
docker exec -it redis redis-cli

# Trong redis-cli:
> KEYS *
> GET live_signals_live_chat_midfeed
> exit
```

### **Kiểm tra PostgreSQL:**
```powershell
# Kết nối Postgres
docker exec -it postgres psql -U phat -d metabaseappdb

# Trong psql:
> SELECT * FROM live_signals LIMIT 5;
> \q
```

---

## 🌐 Truy cập Các Interfaces

| Service | URL | Đăng nhập |
|---------|-----|----------|
| **Spark Master UI** | http://localhost:8080 | Không cần |
| **Streamlit Dashboard** | http://localhost:8501 | Không cần |
| **Metabase BI** | http://localhost:3000 | Tạo account lần đầu |
| **Postgres** | localhost:5432 | user: `phat`, pass: `123456` |
| **Redis** | localhost:6379 | Không cần |

---

## 🛑 Dừng Project

**Khi muốn dừng làm:**

```powershell
# Dừng Consumer (Ctrl+C ở Terminal 2)
# Dừng Producer (Ctrl+C ở Terminal 1)
# Dừng Dashboard (Ctrl+C ở Terminal 3)

# Dừng Docker services
docker-compose down

# (Nếu muốn xóa dữ liệu)
docker-compose down -v
```

---

## ✅ Success Checklist

Khi tất cả chạy OK, bạn sẽ thấy:

- ✅ **Producer Terminal:** Messages từ YouTube/Emulator được gửi đến Kafka
  ```
  ✅ Sent: {'message': 'Hello', 'user': 'user123', ...}
  ```

- ✅ **Consumer Terminal:** Spark nhận và xử lý messages
  ```
  INFO: Processing batch with 50 messages
  INFO: Predictions completed in 1.2s
  ```

- ✅ **Dashboard:** Hiển thị 6 Signals (S1-S6) cập nhật real-time
  ```
  S1 Chat Load: 45 msg/min
  S2 Tech Health: 98%
  S3 Demand Pressure: 8 requests/min
  ...
  ```

- ✅ **Redis:** Có data
  ```
  > GET live_signals_live_chat_midfeed
  "{\"S1\": 45, \"S2\": 0.98, ...}"
  ```

---

## 🔧 Troubleshooting

### **1. "Connection refused" khi tới Kafka**
```powershell
# Kiểm tra Kafka có chạy
docker ps | Select-String "kafka"

# Xem logs
docker logs kafka

# Khởi động lại
docker-compose restart kafka
Start-Sleep -Seconds 30  # Chờ Kafka khởi động
```

### **2. ONNX Models không tìm thấy**
```powershell
# Kiểm tra files tồn tại
ls .\onnx_models\

# Phải có các folder:
# - emotion_encoder_onnx/
# - toxicity_encoder_onnx/
# - interaction_model_onnx/
# - emotion_classifier.onnx
# - toxicity_classifier.onnx
```

### **3. Spark Worker không connect Master**
```powershell
# Kiểm tra Spark logs
docker logs spark-worker

# Restart Spark
docker-compose restart spark-worker spark-master
Start-Sleep -Seconds 30
```

### **4. Dashboard hiển thị "Connection refused Redis"**
```powershell
# Kiểm tra Redis
docker exec redis redis-cli ping
# Phải trả lại: PONG

# Nếu không, restart
docker-compose restart redis
```

### **5. "Address already in use" trên port nào đó**
```powershell
# Kiểm tra port 8501 đã bị dùng
netstat -ano | findstr :8501

# Hoặc tất cả ports khác:
# Kafka: 9092, Spark Master: 8080, 7077, Redis: 6379, Postgres: 5432

# Nếu bị dùng, kill process:
Stop-Process -Id <PID> -Force
```

---

## 📝 Thứ tự chạy các lệnh (Bản tóm tắt)

```powershell
# 1. Build Docker image (lần đầu)
docker build -f Dockerfile.spark -t spark-custom .

# 2. Khởi động services
docker-compose up -d

# 3. Cài Python packages
conda create -n mlops python=3.10 -y
conda activate mlops
pip install -r requirements.txt

# 4.1 Terminal 1: Producer
docker exec kafka kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic live_chat_midfeed --partitions 1 --replication-factor 1
python producer.py --video_id YOUR_LIVE_VIDEO_ID --topic live_chat_midfeed --server localhost:9092

# 4.2 Terminal 2: Consumer
docker exec spark-master spark-submit --master spark://spark-master:7077 --deploy-mode client --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.6.0 /app/consumer.py --kafka-broker kafka:29092 --topic live_chat_midfeed --redis-host redis

# 4.3 Terminal 3: Dashboard
streamlit run dashboard.py

# 5. Truy cập Dashboard
# http://localhost:8501
```

---

**Nếu có bất kỳ lỗi nào, hãy share:**
- Terminal output
- Docker status (`docker ps`)
- Logs: `docker logs <container-name>`

