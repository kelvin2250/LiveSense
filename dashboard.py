import streamlit as st
import redis
import json
import pandas as pd
import time
from datetime import datetime

# 1. Cấu hình trang
st.set_page_config(
    page_title="LiveSense QoE Dashboard",
    page_icon="⚡",
    layout="wide"
)

# 2. Sidebar - Threshold Settings
st.sidebar.title("⚙️ Threshold Settings")
st.sidebar.markdown("Điều chỉnh ngưỡng cảnh báo cho các chỉ số.")

# Ngưỡng cho từng Signal
th_s1 = st.sidebar.slider("S1 - Chat Load (High Load)", 0.0, 100.0, 20.0, help="Cảnh báo khi lượng tin nhắn/phút vượt quá ngưỡng này.")
th_s2 = st.sidebar.slider("S2 - Tech Health (Error Rate)", 0.0, 1.0, 0.1, help="Cảnh báo khi tỉ lệ lỗi kỹ thuật vượt quá ngưỡng.")
th_s3 = st.sidebar.slider("S3 - Demand Pressure", 0.0, 50.0, 10.0, help="Cảnh báo khi nhu cầu người xem tăng cao.")
th_s4 = st.sidebar.slider("S4 - Backseat Pressure", 0.0, 1.0, 0.3, help="Cảnh báo khi tỉ lệ chỉ trích gameplay cao.")
th_s5 = st.sidebar.slider("S5 - Toxic Pressure (Critical)", 0.0, 50.0, 5.0, help="Cảnh báo ĐỎ khi lượng toxic vượt ngưỡng.")
th_s6 = st.sidebar.slider("S6 - Engagement Heat (Viral)", 0.0, 50.0, 15.0, help="Báo hiệu Viral khi tương tác tích cực vượt ngưỡng.")

# 3. Main Content
st.title("⚡ LiveSense QoE - Realtime Signals")
st.markdown("Monitoring **6 Operational Signals** from Spark Streaming via Redis")
st.markdown("---")

# 4. Kết nối Redis
try:
    # Dashboard chạy ở Host nên dùng localhost
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()
except Exception as e:
    st.error(f"❌ Không thể kết nối Redis! Hãy đảm bảo Docker container Redis đang chạy.\nLỗi: {e}")
    st.stop()

# 5. Layout Metrics (2 hàng x 3 cột)
# Tạo placeholder để update dữ liệu mà không reload lại cả trang
col1, col2, col3 = st.columns(3)
col4, col5, col6 = st.columns(3)

metric_s1 = col1.empty()
metric_s2 = col2.empty()
metric_s3 = col3.empty()
metric_s4 = col4.empty()
metric_s5 = col5.empty()
metric_s6 = col6.empty()

st.markdown("---")
st.subheader("📈 Real-time Signal History")
chart_placeholder = st.empty()

# 6. Session State cho Lịch sử
if 'df_history' not in st.session_state:
    st.session_state.df_history = pd.DataFrame(columns=['timestamp', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6'])

def update_dashboard():
    # Lấy dữ liệu từ Redis (Key phải khớp với consumer.py)
    raw_data = redis_client.get("live_signals_streamer_01")
    
    if raw_data:
        data = json.loads(raw_data)
        
        # Parse values
        s1 = data.get('S1_Chat_Load', 0)
        s2 = data.get('S2_Tech_Health', 0)
        s3 = data.get('S3_Demand_Pressure', 0)
        s4 = data.get('S4_Backseat_Pressure', 0)
        s5 = data.get('S5_Toxic_Pressure', 0)
        s6 = data.get('S6_Engagement_Heat', 0)
        total = data.get('total_messages', 0)

        # --- ROW 1 ---
        with metric_s1.container():
            st.metric(
                label="S1 - Chat Load (msg/s)",
                value=s1,
                delta=f"Total: {total}",
                delta_color="inverse" if s1 > th_s1 else "normal"
            )
        
        with metric_s2.container():
            st.metric(
                label="S2 - Tech Health (Error Rate)",
                value=f"{s2:.2%}", # Format phần trăm
                delta="Critical" if s2 > th_s2 else "Stable",
                delta_color="inverse" if s2 > th_s2 else "normal"
            )

        with metric_s3.container():
            st.metric(
                label="S3 - Demand Pressure",
                value=s3,
                delta="High Demand" if s3 > th_s3 else "Normal",
                delta_color="inverse" if s3 > th_s3 else "normal"
            )

        # --- ROW 2 ---
        with metric_s4.container():
            st.metric(
                label="S4 - Backseat Pressure",
                value=f"{s4:.2%}",
                delta="Annoying" if s4 > th_s4 else "Chill",
                delta_color="inverse" if s4 > th_s4 else "normal"
            )

        with metric_s5.container():
            st.metric(
                label="S5 - Toxic Pressure",
                value=s5,
                delta="TOXIC ATTACK" if s5 > th_s5 else "Safe",
                delta_color="inverse" if s5 > th_s5 else "normal"
            )

        with metric_s6.container():
            st.metric(
                label="S6 - Engagement Heat",
                value=s6,
                delta="VIRAL MOMENT 🔥" if s6 > th_s6 else "Normal",
                delta_color="normal" # Green is good
            )

        # --- UPDATE CHART ---
        new_row = {
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'S1': s1, 'S2': s2, 'S3': s3, 'S4': s4, 'S5': s5, 'S6': s6
        }
        
        # Append & Keep last 60 seconds
        st.session_state.df_history = pd.concat([
            st.session_state.df_history, 
            pd.DataFrame([new_row])
        ], ignore_index=True).tail(60)
        
        with chart_placeholder.container():
            # Vẽ biểu đồ line chart với index là timestamp
            st.line_chart(
                st.session_state.df_history.set_index('timestamp')
            )

# Auto-refresh loop
while True:
    update_dashboard()
    time.sleep(1) # Cập nhật mỗi 1 giây