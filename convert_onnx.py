from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer
import onnxruntime as ort
import numpy as np
import torch
import os

# 1. CẤU HÌNH
interaction_labels = [
    'technical_issue',
    'performance_feedback',
    'viewer_request',
    'reaction',
    'other'
]

model_dir = "models/interaction_type"  # Đảm bảo thư mục này có chứa model PyTorch đã train
onnx_save_dir = "onnx_models/onnx_models/interaction_model_onnx"

# ---------------------------------------------------------
# 2. CONVERT & SAVE (Chỉ cần chạy 1 lần)
# ---------------------------------------------------------
print("Dang convert model sang ONNX...")
# Load model và export luôn
onnx_model = ORTModelForSequenceClassification.from_pretrained(
    model_dir,
    export=True
)

# Lưu model và tokenizer
onnx_model.save_pretrained(onnx_save_dir)
tokenizer = AutoTokenizer.from_pretrained(model_dir)
tokenizer.save_pretrained(onnx_save_dir)
print(f"Da luu model ONNX tai: {onnx_save_dir}")

# ---------------------------------------------------------
# 3. LOAD & INFERENCE (Phần này dùng để deploy)
# ---------------------------------------------------------
print("\nDang load model de test...")

# Đường dẫn file model.onnx (Sửa lại chỗ này cho đúng path tương đối)
onnx_model_path = os.path.join(onnx_save_dir, "model.onnx")

# Tạo session (Kiểm tra xem có GPU không)
providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if ort.get_device() == 'GPU' else ["CPUExecutionProvider"]
session = ort.InferenceSession(onnx_model_path, providers=providers)

# Chuẩn bị câu test
text_inputs = ["Hệ thống bị lỗi khi đăng nhập", "tắt mic đi"]

# Tokenize
inputs = tokenizer(
    text_inputs,
    padding=True,
    truncation=True,
    return_tensors="np" # Trả về numpy array luôn
)

# --- MẸO: Tự động lọc input cho khớp với model ONNX ---
# Lấy danh sách tên các input mà model ONNX yêu cầu (thường là input_ids, attention_mask)
onnx_input_names = [node.name for node in session.get_inputs()]

# Chỉ giữ lại các key có trong onnx_input_names và ép kiểu int64
ort_inputs = {
    k: v.astype(np.int64) 
    for k, v in inputs.items() 
    if k in onnx_input_names
}
# ------------------------------------------------------

# Chạy dự đoán
outputs = session.run(None, ort_inputs)
logits = outputs[0]

# Chuyển về xác suất và lấy nhãn
probs = torch.softmax(torch.tensor(logits), dim=-1)
ids = probs.argmax(dim=-1)
preds = [interaction_labels[id] for id in ids]

print("-" * 30)
for text, label, prob in zip(text_inputs, preds, probs):
    confidence = prob[prob.argmax()].item()
    print(f"Text: '{text}'\n -> Label: {label} ({confidence:.2%})\n")