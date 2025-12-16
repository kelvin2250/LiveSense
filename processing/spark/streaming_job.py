from json import load
import sys
import logging
import numpy as np
import pandas as pd
import pyspark.sql.functions as F
from pyspark.sql import SparkSession , DataFrame
from pyspark.sql.types import *
from pyspark.sql.functions import pandas_udf
from typing import Iterator
import torch
from dotenv import load_dotenv
import os
import random
device = 0 if torch.cuda.is_available() else -1
load_dotenv()

# --- CẤU HÌNH MÔI TRƯỜNG (WINDOWS/LINUX) ---
# Nếu chạy trên Windows, cần trỏ tới python.exe trong venv
# Nếu chạy trên Linux/Docker, dòng này có thể bỏ qua hoặc trỏ tới /usr/bin/python3
if sys.platform == "win32":
    os.environ['PYSPARK_PYTHON'] = sys.executable
    os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable

# ==========================================
# 1. SETUP LOGGING
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("YoutubeSparkConsumer")

# ==========================================
# 2. CONFIGURATION CLASS
# ==========================================
class AppConfig:
    # Kafka Config
    KAFKA_BOOTSTRAP = "localhost:9092"
    KAFKA_TOPIC = "youtube_live_chat" 
    
    # Postgres Config
    PG_URL = "jdbc:postgresql://localhost:5432/youtube_db"
    PG_TABLE = "live_chat_sentiment" 
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASS = os.getenv("PG_PASSWORD", "password")
    PG_DRIVER = "org.postgresql.Driver"
    
    # Spark Config
    # Checkpoint là bắt buộc cho Structured Streaming để đảm bảo Fault Tolerance
    CHECKPOINT_DIR = "D:/spark_checkpoints/youtube_nlp" if sys.platform == "win32" else "/tmp/spark_checkpoints/youtube_nlp"

# ==========================================
# 3. UDF DEFINITIONS (NLP Logic)
# ==========================================
@pandas_udf(FloatType())
def analyze_sentiment_udf(text_series: Iterator[pd.Series]) -> Iterator[pd.Series]:
    def get_sentiment(text):
        if not text: 
            return 0.0
        try:
            return np.random.randn()
        except:
            return 0.0

    for series in text_series:
        yield series.apply(get_sentiment)

# ==========================================
# 4. MAIN CONSUMER CLASS
# ==========================================
class YoutubeChatConsumer:
    def __init__(self) -> None:
        self.spark = self._init_spark()
        
        # Schema này PHẢI khớp với dữ liệu JSON từ Producer gửi lên
        self.schema = StructType([
            StructField("id", StringType()),
            StructField("video_id", StringType()),
            StructField("author", StringType()),
            StructField("text", StringType()),
            StructField("published_at", StringType()),
            StructField("source", StringType()),
            StructField("is_chat_owner", BooleanType()),
            StructField("is_chat_moderator", BooleanType())
        ])

    def _init_spark(self):
        logger.info("Initializing Spark Session...")
        kafka_pkg = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.7"
        postgres_pkg = "org.postgresql:postgresql:42.6.0"
        
        try:
            spark = SparkSession.builder \
                .appName("YoutubeSentimentAnalysis") \
                .config("spark.jars.packages", f"{kafka_pkg},{postgres_pkg}") \
                .config("spark.sql.shuffle.partitions", "4") \
                .getOrCreate()
            return spark
        except Exception as e:
            logger.error(f"Critical Error: Failed to init Spark: {e}")
            sys.exit(1)

    def read_stream(self):
        """Đọc dữ liệu thô từ Kafka"""
        logger.info(f"Subscribing to Kafka topic: {AppConfig.KAFKA_TOPIC}")
        
        raw_df = self.spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", AppConfig.KAFKA_BOOTSTRAP) \
            .option("subscribe", AppConfig.KAFKA_TOPIC) \
            .option("startingOffsets", "latest") \
            .load()
        
        # Kafka trả về binary (key, value), ta cần cast value sang String
        return raw_df.selectExpr("CAST(value AS STRING) as json_str")

    def process_stream(self, df_stream: DataFrame):
        """
        Parse JSON -> Transform Data -> Apply AI/ML (Sentiment)
        """
        # 1. Parse JSON thành các cột
        parsed_df = df_stream.select(
            F.from_json(F.col("json_str"), self.schema).alias("data")
        ).select("data.*")

        # 2. Data Cleaning & Type Casting
        # Chuyển đổi published_at từ String ISO sang Timestamp chuẩn
        cleaned_df = parsed_df.withColumn(
            "published_at", 
            F.to_timestamp(F.col("published_at"))
        )

        # 3. Feature Engineering: Áp dụng UDF Sentiment Analysis
        logger.info("Attaching Sentiment Analysis UDF...")
        final_df = cleaned_df.withColumn(
            "sentiment_score", 
            analyze_sentiment_udf(F.col("text"))
        ).withColumn(
            "sentiment_label",
            F.when(F.col("sentiment_score") > 0.2, "POSITIVE")
             .when(F.col("sentiment_score") < -0.2, "NEGATIVE")
             .otherwise("NEUTRAL")
        )

        final_df = final_df.withColumn("content", F.col('text')) 

        # 4. Chọn các cột cuối cùng để lưu
        return final_df.select(
            F.col("id"),
            F.col("video_id"),
            F.col("published_at"),
            F.col("author"),
            F.col("content"),
            F.col("sentiment_score"),
            F.col("sentiment_label"),
            F.col("source")
        )

    @staticmethod
    def _write_to_postgres(batch_df: DataFrame, batch_id: int):
        """Hàm ghi dữ liệu xuống DB cho từng Batch"""
        if batch_df.isEmpty():
            return

        logger.info(f"⚡ Batch {batch_id}: Writing {batch_df.count()} records to Postgres...")
        
        jdbc_url = AppConfig.PG_URL
        jdbc_props = {
            "user": AppConfig.PG_USER,
            "password": AppConfig.PG_PASS,
            "driver": AppConfig.PG_DRIVER
        }
        
        try:
            batch_df.write \
                .mode("append") \
                .jdbc(url=jdbc_url, table=AppConfig.PG_TABLE, properties=jdbc_props)
            logger.info(f"✅ Batch {batch_id} commited successfully.")
        except Exception as e:
            logger.error(f"❌ Batch {batch_id} failed: {e}")

    def start(self):
        """Khởi động Pipeline"""
        raw_stream = self.read_stream()
        processed_stream = self.process_stream(raw_stream)
        
        logger.info("🚀 Starting Spark Structured Streaming...")
        
        query = processed_stream.writeStream \
            .foreachBatch(self._write_to_postgres) \
            .option("checkpointLocation", AppConfig.CHECKPOINT_DIR) \
            .trigger(processingTime='20 seconds') \
            .outputMode("append") \
            .start()

        try:
            query.awaitTermination()
        except KeyboardInterrupt:
            logger.info("🛑 Stopping query via KeyboardInterrupt")
            query.stop()

# ==========================================
# 5. ENTRY POINT
# ==========================================
if __name__ == "__main__":
    consumer = YoutubeChatConsumer()
    consumer.start()


# run : python streaming_job.py 

#  cd LiveSense\processing\spark