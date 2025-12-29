import json, redis
import builtins
import random
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *

# ======================
# 1) SPARK SESSION (Docker)
# ======================
spark = SparkSession.builder \
    .appName("LiveSense-QoE-Docker") \
    .master("spark://spark-master:7077") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.0,org.postgresql:postgresql:42.7.3") \
    .config("spark.driver.extraJavaOptions", "-Duser.home=/home/spark") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# 2) REDIS KẾT NỐI TRONG DOCKER
redis_client = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)

# 3) SCHEMA DỮ LIỆU KAFKA
chat_schema = StructType([
    StructField("id", IntegerType()),
    StructField("author", StringType()),
    StructField("message", StringType()),
    StructField("timestamp", TimestampType()),
    StructField("platform", StringType())
])
# 4) LOGIC DỰ ĐOÁN / SIGNAL
import random
import json
import builtins
from datetime import datetime

def process_batch(batch_df, batch_id):
    if batch_df.isEmpty():
        return
    
    # Chuyển đổi sang Pandas để xử lý logic tính toán
    df = batch_df.toPandas()
    total = len(df)
    
    # ==========================================
    # 1. GIẢ LẬP AI LABELING (MOCKUP DATA)
    # ==========================================
    # Các nhãn này sau này sẽ được thay thế bởi 3 model của bạn
    interaction_opts = ['Technical_issue', 'Performance_feedback', 'Viewer_request', 'Reaction', 'other']
    emotion_opts = ['Neutral', 'Excitement', 'Frustration', 'Disappointment']
    toxic_opts = ['Clean', 'Playful_toxic', 'Aggressive_Toxic', 'Severe_Toxic']

    # Gán nhãn ngẫu nhiên có trọng số (để dữ liệu thực tế hơn một chút)
    df["interaction_type"] = [random.choices(interaction_opts, weights=[5, 15, 10, 40, 30])[0] for _ in range(total)]
    df["emotion"] = [random.choices(emotion_opts, weights=[50, 20, 15, 15])[0] for _ in range(total)]
    df["toxicity"] = [random.choices(toxic_opts, weights=[70, 15, 10, 5])[0] for _ in range(total)]

    # ==========================================
    # 2. TÍNH TOÁN CÁC OPERATIONAL SIGNALS (S1 - S6)
    # ==========================================
    
    # S1) Chat Load: Tổng tin nhắn / 60s (msg/s)
    s1_chat_load = total / 60

    # S2) Stream Tech Health: Tỉ lệ lỗi kỹ thuật trên tổng số message
    tech_count = len(df[df["interaction_type"] == "Technical_issue"])
    s2_tech_health = tech_count / total if total > 0 else 0

    # S3) Viewer Demand Pressure: Tải lượng yêu cầu từ người xem / 60s
    request_count = len(df[df["interaction_type"] == "Viewer_request"])
    s3_demand_pressure = request_count / 60

    # S4) Backseat / Criticism Pressure: Tỉ lệ chỉ trích cách chơi
    criticism_count = len(df[df["interaction_type"] == "Performance_feedback"])
    s4_backseat_pressure = criticism_count / total if total > 0 else 0

    # S5) Toxic Attack Pressure: Tin nhắn tấn công (Aggressive/Severe) / 60s
    toxic_attack_count = len(df[df["toxicity"].isin(["Aggressive_Toxic", "Severe_Toxic"])])
    s5_toxic_pressure = toxic_attack_count / 60

    # S6) Engagement Heat: Khoảnh khắc cao trào (Reaction HOẶC Excitement) / 60s
    # Fix: Kết hợp cả Interaction Type là Reaction và Emotion là Excitement
    engagement_count = len(df[(df["interaction_type"] == "Reaction") | (df["emotion"] == "Excitement")])
    s6_engagement_heat = engagement_count / 60

    # 3. ĐÓNG GÓI VÀ ĐẨY DỮ LIỆU LÊN REDIS
    signals = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "total_messages": total,
        "S1_Chat_Load": builtins.round(s1_chat_load, 4),
        "S2_Tech_Health": builtins.round(s2_tech_health, 4),
        "S3_Demand_Pressure": builtins.round(s3_demand_pressure, 4),
        "S4_Backseat_Pressure": builtins.round(s4_backseat_pressure, 4),
        "S5_Toxic_Pressure": builtins.round(s5_toxic_pressure, 4),
        "S6_Engagement_Heat": builtins.round(s6_engagement_heat, 4)
    }

    # Lưu vào Redis để Dashboard Real-time có thể fetch
    try:
        redis_client.set("live_signals_streamer_01", json.dumps(signals))
        print(f"✅ Batch {batch_id} processed. Signals updated in Redis.")
        print(f"📊 {signals}")
    except Exception as e:
        print(f"❌ Error updating Redis: {e}")

    # 4. LƯU XUỐNG POSTGRES (HISTORICAL ANALYSIS)
    try:
        # A) Lưu Raw Data + AI Labels (Bảng chi tiết)
        enriched_df = spark.createDataFrame(df)
        
        enriched_df.write \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://postgres:5432/metabaseappdb") \
            .option("dbtable", "chat_history_analysis") \
            .option("user", "phat") \
            .option("password", "123456") \
            .option("driver", "org.postgresql.Driver") \
            .mode("append") \
            .save()
            
        # B) Lưu Signals theo thời gian (Bảng tổng hợp)
        # Tạo DataFrame 1 dòng chứa các signal
        signals_df = spark.createDataFrame([signals])
        
        signals_df.write \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://postgres:5432/metabaseappdb") \
            .option("dbtable", "stream_signals_history") \
            .option("user", "phat") \
            .option("password", "123456") \
            .option("driver", "org.postgresql.Driver") \
            .mode("append") \
            .save()

        print(f"💾 Batch {batch_id} saved to Postgres (Tables: chat_history_analysis & stream_signals_history).")
    except Exception as e:
        print(f"❌ Error saving to Postgres: {e}")


raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:29092") \
    .option("subscribe", "live_chat_laibang") \
    .option("startingOffsets", "latest") \
    .load()

chat_df = raw_stream.selectExpr("CAST(value as STRING)") \
          .select(from_json(col("value"), chat_schema).alias("data")) \
          .select("data.*")

query = chat_df.writeStream \
    .foreachBatch(process_batch) \
    .trigger(processingTime="0.5 seconds") \
    .option("checkpointLocation", "/tmp/spark-checkpoints") \
    .start()

print("🚀 Spark Streaming is running inside Docker...")
query.awaitTermination()
