import sys
import argparse
import json
import redis
import builtins
import traceback
import os
import pandas as pd
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *

try:
    from onnx_inference import ONNXSetFitPredictor, ONNXAutoModelClassifier
    print("✅ Imported onnx_inference module successfully.")
except ImportError as e:
    print(f"❌ Error importing onnx_inference: {e}")
    sys.exit(1)

# ==========================================
# 1. GLOBAL MODEL INITIALIZATION (LOAD ONCE)
# ==========================================
# Auto-detect ONNX directory for both Docker and local Windows/Linux runs.
DOCKER_ONNX_DIR = "/app/onnx_models"
LOCAL_ONNX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "onnx_models")
ONNX_DIR = DOCKER_ONNX_DIR if os.path.isdir(DOCKER_ONNX_DIR) else LOCAL_ONNX_DIR

print("🧠 Loading ONNX Models...")
try:
    toxicity_predictor = ONNXSetFitPredictor(
        encoder_path=os.path.join(ONNX_DIR, "toxicity_encoder_onnx"),
        classifier_path=os.path.join(ONNX_DIR, "toxicity_classifier.onnx"),
        labels_path=os.path.join(ONNX_DIR, "toxicity_labels.txt")
    )

    emotion_predictor = ONNXSetFitPredictor(
        encoder_path=os.path.join(ONNX_DIR, "emotion_encoder_onnx"),
        classifier_path=os.path.join(ONNX_DIR, "emotion_classifier.onnx"),
        labels_path=os.path.join(ONNX_DIR, "emotion_labels.txt")
    )

    interaction_predictor = ONNXAutoModelClassifier(
        model_path=os.path.join(ONNX_DIR, "interaction_model_onnx", "model.onnx"),
        tokenizer_path=os.path.join(ONNX_DIR, "interaction_model_onnx"),
        labels=['Technical_issue', 'Performance_feedback', 'Viewer_request', 'Reaction', 'Other']
    )
    print("✅ All ONNX models loaded successfully!")

except Exception as e:
    print(f"🔥 Critical Error loading models: {e}")
    traceback.print_exc()
    sys.exit(1) 

# ==========================================
# 2. PIPELINE CLASS
# ==========================================
class LiveSensePipeline:
    def __init__(self, args):
        self.args = args
        self.topic = args.topic
        
        print("⚙️  Initializing Spark Session...")
        self.spark = SparkSession.builder \
            .appName(f"LiveSense-Consumer-{self.topic}") \
            .master("spark://spark-master:7077") \
            .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.6.0") \
            .config("spark.driver.extraJavaOptions", "-Duser.home=/home/spark") \
            .config("spark.sql.shuffle.partitions", "4") \
            .getOrCreate()
        
        self.spark.sparkContext.setLogLevel("WARN")
        
        self.redis_client = None
        self._init_redis()

        self.db_url = "jdbc:postgresql://postgres:5432/metabaseappdb"
        self.db_props = {"user": "phat", "password": "123456", "driver": "org.postgresql.Driver"}

    def _init_redis(self):
        try:
            self.redis_client = redis.Redis(
                host=self.args.redis_host,
                port=self.args.redis_port,
                db=0,
                decode_responses=True
            )
            self.redis_client.ping()
            print("✅ Connected to Redis successfully.")
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}")

    def get_schema(self):
        return StructType([
            StructField("id", StringType()),
            StructField("video_id", StringType()),
            StructField("author", StringType()),
            StructField("message", StringType()),
            StructField("timestamp", TimestampType()),
            StructField("platform", StringType())
        ])

    def enrich_data(self, df):
        """
        SỬ DỤNG MODEL THẬT ĐỂ DỰ ĐOÁN
        """
        if df.empty: return df
        
        messages = df["message"].astype(str).tolist()
        
        try:
            df["toxicity"] = toxicity_predictor.predict(messages)

            df["emotion"] = emotion_predictor.predict(messages)
            
            df["interaction_type"] = interaction_predictor.predict(messages)

        except Exception as e:
            print(f"⚠️ Inference Error: {e}")
            traceback.print_exc()
            df["toxicity"] = "Unknown"
            df["emotion"] = "Neutral"
            df["interaction_type"] = "Other"
            
        return df

    def calculate_signals(self, df):
        total = len(df)
        if total == 0: return None

        signals = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "total_messages": total,
            "S1_Chat_Load": builtins.round(total / 60, 4),
            "S2_Tech_Health": builtins.round(len(df[df["interaction_type"] == "Technical_issue"]) / total, 4),
            "S3_Demand_Pressure": builtins.round(len(df[df["interaction_type"] == "Viewer_request"]) / 60, 4),
            "S4_Backseat_Pressure": builtins.round(len(df[df["interaction_type"] == "Performance_feedback"]) / total, 4),
            "S5_Toxic_Pressure": builtins.round(len(df[df["toxicity"].isin(["Aggressive_Toxic", "Severe_Toxic"])]) / 60, 4),
            "S6_Engagement_Heat": builtins.round(len(df[(df["interaction_type"] == "Reaction") | (df["emotion"] == "Excitement")]) / 60, 4)
        }
        return signals

    def save_to_redis(self, signals, batch_id):
        if not self.redis_client or not signals: return
        try:
            redis_key = f"live_signals_{self.topic}"
            self.redis_client.set(redis_key, json.dumps(signals))
            print(f"✅ Batch {batch_id}: Redis updated.")
        except Exception as e:
            print(f"❌ Redis Error: {e}")

    def save_to_postgres(self, pandas_df, signals, batch_id):
        try:
            spark_df = self.spark.createDataFrame(pandas_df)

            final_df = spark_df.select(
                col("id"), 
                "video_id", "author", "message", 
                "timestamp", "platform", "emotion", 
                "toxicity", "interaction_type"
            )
            
            final_df.write.jdbc(
                url=self.db_url, table="chat_history_analysis", 
                mode="append", properties=self.db_props
            )
            
            if signals:
                signals_df = self.spark.createDataFrame([signals])
                signals_df.write.jdbc(
                    url=self.db_url, table="stream_signals_history", 
                    mode="append", properties=self.db_props
                )
            print(f"💾 Batch {batch_id}: Saved to Postgres.")
        except Exception as e:
            print(f"❌ Postgres Error: {e}")

    def process_batch_driver(self, batch_df, batch_id):
        if batch_df.isEmpty(): return
        print(f"\n--- Processing Batch {batch_id} ---")
        try:
            pdf = batch_df.toPandas()
            pdf = self.enrich_data(pdf)  
            signals = self.calculate_signals(pdf)
            self.save_to_redis(signals, batch_id)
            self.save_to_postgres(pdf, signals, batch_id)
        except Exception as e:
            print(f"🔥 Critical Error in Batch {batch_id}: {e}")
            traceback.print_exc()

    def run(self):
        print(f"🚀 Starting Stream for Topic: {self.topic}")
        raw_stream = self.spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", self.args.kafka_servers) \
            .option("subscribe", self.topic) \
            .option("maxOffsetsPerTrigger", 16) \
            .option("startingOffsets", "earliest") \
            .option("failOnDataLoss", "false") \
            .load()

        parsed_stream = raw_stream.selectExpr("CAST(value as STRING)") \
            .select(from_json(col("value"), self.get_schema()).alias("data")) \
            .select("data.*")

        checkpoint_path = f"{self.args.checkpoint_dir}/{self.topic}"
        
        query = parsed_stream.writeStream \
            .foreachBatch(self.process_batch_driver) \
            .trigger(processingTime="2 seconds") \
            .option("checkpointLocation", checkpoint_path) \
            .start()

        print(f"🌊 Stream is Active. Checkpoint: {checkpoint_path}")
        try:
            query.awaitTermination()
        except KeyboardInterrupt:
            query.stop()

def get_args():
    parser = argparse.ArgumentParser(description="LiveSense Class-based Consumer")
    parser.add_argument("--topic", required=True, help="Kafka topic name")
    parser.add_argument("--checkpoint-dir", default="/tmp/spark-checkpoints", help="Checkpoint root dir")
    parser.add_argument(
        "--kafka_servers", "--kafka-broker",
        dest="kafka_servers",
        default="kafka:29092",
        help="Kafka bootstrap servers"
    )
    parser.add_argument("--redis-host", default="redis", help="Redis host")
    parser.add_argument("--redis-port", type=int, default=6379, help="Redis port")
    return parser.parse_args()  

if __name__ == "__main__":
    args = get_args()
    pipeline = LiveSensePipeline(args)
    pipeline.run()