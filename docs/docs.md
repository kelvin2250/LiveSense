Chào bạn, mình sẽ hướng dẫn chi tiết từng bước để bạn vận hành hệ thống này (End-to-End), cũng như giải đáp các thắc mắc về Postgres và Redis.

---

### 1. Hướng dẫn chạy End-to-End Service

Để hệ thống chạy mượt mà từ lúc khởi động đến lúc xử lý dữ liệu, bạn làm theo quy trình chuẩn sau:

#### Bước 1: Build Custom Image cho Spark

Do bạn có file `Dockerfile.spark` để cài thêm thư viện python (`kafka-python`, `redis`...), bạn cần build nó trước.
Mở terminal tại thư mục chứa file và chạy:

```bash
# -f chỉ định tên file dockerfile, -t đặt tên ảnh là spark-custom
docker build -t spark-custom -f Dockerfile.spark .

```

#### Bước 2: Khởi động hệ thống (Docker Compose)

Sau khi build xong, chạy file compose:

```bash
docker-compose up -d

```

* Dùng lệnh `docker ps` để đảm bảo tất cả container (`kafka`, `spark-master`, `spark-worker`, `postgres`, `redis`...) đều có trạng thái **Up**.

#### Bước 3: Chuẩn bị Database (Optional)

Mặc dù container Postgres tự tạo DB mặc định, nhưng tốt nhất nên tạo một DB riêng cho data của Spark để không lẫn với data của Metabase (sẽ giải thích kỹ ở phần 3).

```bash
# Tạo database tên là "spark_data"
docker exec -it postgres psql -U phat -d metabaseappdb -c "CREATE DATABASE spark_data;"

```

#### Bước 4: Submit Spark Job (Consumer)

Job này sẽ chạy ngầm trong Spark Worker, lắng nghe Kafka.
*(Bạn cần chuẩn bị file `consumer.py` để trong thư mục hiện tại - xem mẫu code ở phần trước).*

```bash
# Lệnh này gửi job vào spark-master container
docker exec -d spark-master /opt/spark/bin/spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.6.0 \
  /app/consumer.py

```

*Lưu ý: `-d` (detach) giúp lệnh chạy ngầm, không chiếm dụng terminal của bạn.*

---

### 2. Cách chạy Producer Script submit vào Kafka

Có 2 cách để chạy Producer, nhưng cách phổ biến nhất khi dev là chạy **từ máy thật (Host Machine)** của bạn đẩy vào **Docker container**.

**Tại sao chạy từ máy thật?**
Vì Producer thường mô phỏng dữ liệu từ bên ngoài (IoT sensor, Web API...) nên nó nằm ngoài cluster là hợp lý.

**Thực hiện:**

1. **Cài thư viện trên máy thật:**
Bạn cần cài Python và thư viện kafka:
```bash
pip install kafka-python

```


2. **Viết Script Producer (`producer.py`):**
Quan trọng nhất là `bootstrap_servers`. Vì chạy từ ngoài vào docker, bạn phải gọi vào port `9092` (đã được expose trong file yml).
```python
import json
import time
import random
from kafka import KafkaProducer

# KẾT NỐI QUA LOCALHOST:9092
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'], 
    value_serializer=lambda x: json.dumps(x).encode('utf-8')
)

TOPIC_NAME = 'sensor_data'

print("Bắt đầu gửi dữ liệu...")
try:
    while True:
        data = {
            'id': random.randint(1, 100),
            'temp': round(random.uniform(20.5, 30.5), 2),
            'ts': int(time.time())
        }
        producer.send(TOPIC_NAME, value=data)
        print(f"Đã gửi: {data}")
        time.sleep(1) # Gửi mỗi 1 giây
except KeyboardInterrupt:
    print("Đã dừng.")

```


3. **Chạy script:**
```bash
python producer.py

```


*Lúc này dữ liệu sẽ đi từ Máy thật -> Port 9092 -> Container Kafka -> Lưu vào topic `sensor_data`.*

---

### 3. Ghi xuống Postgres: Có cần vào Container tạo DB không?

Câu trả lời là: **Có và Không (Tùy trường hợp).**

#### Trường hợp 1: Database (Cơ sở dữ liệu) - CẦN

Trong file docker-compose của bạn:

```yaml
environment:
  POSTGRES_DB: metabaseappdb

```

Khi container chạy lần đầu, nó **tự động** tạo DB tên là `metabaseappdb`.

* Nếu bạn muốn Spark ghi chung vào `metabaseappdb` -> **Không cần tạo gì thêm.**
* Nếu bạn muốn Spark ghi vào một DB khác (ví dụ `spark_warehouse`) -> **Bạn PHẢI tạo DB này thủ công** (như lệnh ở Bước 3 phần 1). Spark không thể tự tạo Database (`CREATE DATABASE`), nó chỉ tạo được Bảng (`CREATE TABLE`).

#### Trường hợp 2: Table (Bảng) - KHÔNG CẦN

Spark rất thông minh. Khi bạn ghi dữ liệu (DataFrame) xuống Postgres, nếu bảng chưa tồn tại, Spark sẽ tự tạo bảng dựa trên schema của DataFrame.

Code Spark mẫu để tự tạo bảng:

```python
# df là dữ liệu đã xử lý
df.write \
    .format("jdbc") \
    .option("url", "jdbc:postgresql://postgres:5432/spark_data") \
    .option("dbtable", "public.sensor_readings") \
    .option("user", "phat") \
    .option("password", "123456") \
    .option("driver", "org.postgresql.Driver") \
    .mode("append") \
    .save()

```

* `mode("append")`: Nếu bảng chưa có -> Tự tạo. Nếu có rồi -> Ghi nối tiếp vào.
* `mode("overwrite")`: Xóa bảng cũ -> Tạo bảng mới.

---

### 4. Giải thích cơ chế Redis trong hệ thống này

Redis đóng vai trò là **Bộ nhớ đệm tốc độ cao (In-memory Cache)**.

#### Tại sao cần Redis khi đã có Postgres?

Postgres lưu vào ổ cứng (Disk), Redis lưu trên RAM.

* **Postgres:** Tốt cho lưu trữ lâu dài, truy vấn phức tạp (SQL), dữ liệu lịch sử. Nhưng ghi/đọc chậm hơn RAM.
* **Redis:** Tốc độ cực nhanh (micro-seconds). Dữ liệu mất khi tắt máy (nếu không cấu hình save).

#### Cơ chế hoạt động trong luồng Data Pipeline của bạn:

1. **Real-time Dashboarding (Bảng điều khiển thời gian thực):**
* Giả sử bạn muốn hiện "Nhiệt độ hiện tại" lên Web.
* Nếu hàng nghìn người xem cùng lúc mà query vào Postgres -> Postgres quá tải.
* **Giải pháp:** Spark sau khi xử lý xong 1 dòng data mới nhất -> Ghi đè vào Redis (Key: `current_temp`, Value: `30.5`). Website chỉ cần đọc Redis (siêu nhẹ).


2. **Deduplication (Chống trùng lặp):**
* Kafka có thể gửi trùng tin nhắn.
* Trước khi xử lý, Spark check trong Redis xem ID tin nhắn này đã xử lý chưa (Redis trả lời cực nhanh). Nếu chưa -> Xử lý & lưu ID vào Redis. Nếu rồi -> Bỏ qua.


3. **Cửa sổ trượt (Sliding Window):**
* Tính toán trung bình trong 5 phút gần nhất. Redis có cấu trúc List/Sorted Set rất hợp để lưu tạm 5 phút dữ liệu này để tính toán nhanh.



**Tóm lại sơ đồ dữ liệu:**

```
[Kafka] ---> [Spark] ---> [Postgres] (Lưu trữ lâu dài, làm báo cáo tháng/năm)
                  |
                  +-----> [Redis] (Lưu trạng thái mới nhất, phục vụ web realtime)

```