"""
Integration code for using ONNX models in process_batch function.

This module provides the setup and integration code to use ONNX-converted
SetFit models for toxicity and emotion classification in the streaming pipeline.
"""

import os
import random
import builtins
from datetime import datetime
from onnx_inference import ONNXSetFitPredictor, ONNXAutoModelClassifier
from time import time

# ==========================================
# ONNX MODEL INITIALIZATION (DO THIS ONCE)
# ==========================================

# Path to ONNX models
ONNX_DIR = r"D:\Projects\Assignment\Systems\Trading System\notebooks\onnx_models"

# Initialize toxicity predictor
toxicity_predictor = ONNXSetFitPredictor(
    encoder_path=os.path.join(ONNX_DIR, "toxicity_encoder_onnx"),
    classifier_path=os.path.join(ONNX_DIR, "toxicity_classifier.onnx"),
    labels_path=os.path.join(ONNX_DIR, "toxicity_labels.txt")
)

# Initialize emotion predictor
emotion_predictor = ONNXSetFitPredictor(
    encoder_path=os.path.join(ONNX_DIR, "emotion_encoder_onnx"),
    classifier_path=os.path.join(ONNX_DIR, "emotion_classifier.onnx"),
    labels_path=os.path.join(ONNX_DIR, "emotion_labels.txt")
)

# Initialize interaction predictor
interaction_predictor = ONNXAutoModelClassifier(
        model_path=r"D:\Projects\Assignment\Systems\Trading System\notebooks\interaction_model_onnx\model.onnx",
        tokenizer_path=r"D:\Projects\Assignment\Systems\Trading System\notebooks\interaction_tokenizer_onnx",
        labels=['technical_issue',
                    'performance_feedback',
                    'viewer_request',
                    'reaction',
                    'other']
    )

print("✓ ONNX models loaded successfully!")


# ==========================================
# UPDATED process_batch FUNCTION
# ==========================================

def process_batch(batch_df, batch_id):
    """
    Process a batch of chat messages with ML-based classification.
    
    Uses ONNX models for toxicity and emotion classification,
    then calculates operational signals (S1-S6).
    """
    if batch_df.isEmpty():
        return
    
    df = batch_df.toPandas()
    total = len(df)
    
    messages = df["message"].tolist()  

    print(f"Processing batch {batch_id} with {total} messages...")
    start = time()
    toxicity_labels = toxicity_predictor.predict(messages)
    emotion_labels = emotion_predictor.predict(messages)
    interaction_labels = interaction_predictor.predict(messages)

    end = time()
    print(f"Batch {batch_id} inferenced in {end - start:.2f} seconds")

    df["toxicity"] = toxicity_labels
    df["emotion"] = emotion_labels
    df["interaction_type"] = interaction_labels
    
    # ==========================================
    # 2. CALCULATE OPERATIONAL SIGNALS (S1 - S6)
    # ==========================================
    
    # S1) Chat Load: Total messages / 60s (msg/s)
    s1_chat_load = total / 60
    
    # S2) Stream Tech Health: Technical issue ratio
    tech_count = len(df[df["interaction_type"] == "Technical_issue"])
    s2_tech_health = tech_count / total if total > 0 else 0
    
    # S3) Viewer Demand Pressure: Request load / 60s
    request_count = len(df[df["interaction_type"] == "Viewer_request"])
    s3_demand_pressure = request_count / 60
    
    # S4) Backseat / Criticism Pressure: Performance feedback ratio
    criticism_count = len(df[df["interaction_type"] == "Performance_feedback"])
    s4_backseat_pressure = criticism_count / total if total > 0 else 0
    
    # S5) Toxic Attack Pressure: Aggressive toxic messages / 60s
    # Note: Adjust based on your actual toxicity labels
    toxic_attack_count = len(df[df["toxicity"] == "Aggressive_Toxic"])
    s5_toxic_pressure = toxic_attack_count / 60
    
    # S6) Engagement Heat: High engagement moments / 60s
    # Reaction OR Excitement
    engagement_count = len(df[(df["interaction_type"] == "Reaction") | (df["emotion"] == "Excitement")])
    s6_engagement_heat = engagement_count / 60
    
    # ==========================================
    # 3. PACKAGE AND PUSH TO REDIS
    # ==========================================
    
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
    
    # TODO: Push signals to Redis
    # redis_client.set("stream_signals", json.dumps(signals))
    
    print(f"Batch {batch_id} processed: {signals}")
    
    return signals


# ==========================================
# EXAMPLE USAGE
# ==========================================

if __name__ == "__main__":
    import pandas as pd
    
    # Create sample data
    sample_messages = [
        "ngu vcl chè ơi",
        "Hi e chè",
        "m muốn lấy chợ lớn ????",
        "đánh ngu c",
        "ăn lol gì mà ngu vậy",
        "đần",
        "chết mẹ đi cho rồi",
        "dốt ác :))"
    ]
    
    sample_df = pd.DataFrame({
        "message": sample_messages,
        "timestamp": [datetime.now()] * len(sample_messages)
    })
    
    class MockSparkDF:
        def __init__(self, pandas_df):
            self.pandas_df = pandas_df
        
        def isEmpty(self):
            return len(self.pandas_df) == 0
        
        def toPandas(self):
            return self.pandas_df
    
    mock_batch = MockSparkDF(sample_df)
    
    result = process_batch(mock_batch, batch_id=1)
    
    print("\\n" + "="*60)
    print("PROCESSING COMPLETE")
    print("="*60)
    print(f"Signals: {result}")


#python process_batch_integration.py