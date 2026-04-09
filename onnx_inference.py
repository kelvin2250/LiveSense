import os
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer
from typing import List, Union
import torch 

class ONNXPredictor:
    def predict(self, texts: Union[str, List[str]]) -> Union[str, List[str]]:
        raise NotImplementedError


def _select_providers() -> list:
    available = set(ort.get_available_providers())
    if "CUDAExecutionProvider" in available:
        return [("CUDAExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]

class ONNXAutoModelClassifier:
    def __init__(self, model_path: str , tokenizer_path : str, labels : list):
        """
        Initialize the ONNX predictor (AutoModelForSequenceClassification).
        
        Args:
            model_path: Path to the ONNX model file (.onnx)
        """
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        self.session = ort.InferenceSession(
            model_path,
            providers=_select_providers()
        )
        self.labels = labels

        print(f"✓ Model loaded from: {model_path}")
        print(f"✓ Labels : {self.labels}")
    def predict(self, texts: Union[str, List[str]]) -> Union[str, List[str]]:
        """ 
        Args:
            texts: Single text string or list of text strings
        
        Returns:
            Single label or list of labels
        """
        # xử lý single 

        single_input = isinstance(texts, str)
        if single_input:
            texts = [texts]

        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="np"
        )

        inputs = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64)
        }
        
        outputs = self.session.run(None, dict(inputs))
        logits = outputs[0]
        ids = torch.softmax(torch.tensor(logits), dim = -1).argmax(dim = -1)

        preds = [self.labels[id] for id in ids]

        if single_input:
            return preds[0]

        return preds

class ONNXSetFitPredictor(ONNXPredictor):
    """
    ONNX-based predictor for SetFit models.
    Handles tokenization, encoding, and classification in a single pipeline.
    """
    def __init__(self, encoder_path: str, classifier_path: str, labels_path: str):
        """
        Initialize the ONNX predictor.
        
        Args:
            encoder_path: Path to the ONNX encoder directory (contains model.onnx)
            classifier_path: Path to the ONNX classifier file (.onnx)
            labels_path: Path to the labels text file
        """
        print(f"Loading ONNX models...")
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(encoder_path)
        
        # Load ONNX encoder
        encoder_model_path = os.path.join(encoder_path, "model.onnx")
        self.encoder_session = ort.InferenceSession(
            encoder_model_path,
            providers=_select_providers()
        )
        
        # Load ONNX classifier
        self.classifier_session = ort.InferenceSession(
            classifier_path,
            providers=_select_providers()
        )
        
        # Load labels
        with open(labels_path, "r", encoding="utf-8") as f:
            self.labels = [line.strip() for line in f.readlines()]
        
        print(f"✓ Encoder loaded from: {encoder_model_path}")
        print(f"✓ Classifier loaded from: {classifier_path}")
        print(f"✓ Labels loaded: {self.labels}")
    
    def _mean_pooling(self, embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
        """
        Apply mean pooling to get sentence embeddings.
        
        Args:
            embeddings: Token embeddings [batch_size, seq_len, hidden_dim]
            attention_mask: Attention mask [batch_size, seq_len]
        
        Returns:
            Sentence embeddings [batch_size, hidden_dim]
        """
        # Expand attention mask to match embeddings shape
        mask_expanded = np.expand_dims(attention_mask, -1)
        
        # Sum embeddings where mask is 1
        sum_embeddings = np.sum(embeddings * mask_expanded, axis=1)
        
        # Sum mask values (number of real tokens)
        sum_mask = np.clip(np.sum(attention_mask, axis=1, keepdims=True), a_min=1e-9, a_max=None)
        
        # Compute mean
        sentence_embeddings = sum_embeddings / sum_mask
        
        return sentence_embeddings
    
    def predict(self, texts: Union[str, List[str]]) -> Union[str, List[str]]:
        """
        Predict labels for input texts.
        
        Args:
            texts: Single text string or list of text strings
        
        Returns:
            Single label or list of labels
        """
        # Handle single text input
        single_input = isinstance(texts, str)
        if single_input:
            texts = [texts]
        
        # Tokenize
        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="np"
        )
        
        # Prepare encoder inputs
        encoder_inputs = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64)
        }
        
        # Run encoder
        encoder_outputs = self.encoder_session.run(None, encoder_inputs)
        token_embeddings = encoder_outputs[0]  # [batch_size, seq_len, hidden_dim]
        
        # Apply mean pooling
        sentence_embeddings = self._mean_pooling(
            token_embeddings,
            inputs["attention_mask"]
        )
        
        # Run classifier
        classifier_inputs = {"float_input": sentence_embeddings.astype(np.float32)}
        classifier_outputs = self.classifier_session.run(None, classifier_inputs)
        pred_indices = classifier_outputs[0]  

        # Some exported sklearn classifiers already output string labels.
        if isinstance(pred_indices[0], str):
           predictions = pred_indices

        else:# Convert indices to labels
           predictions = [self.labels[idx] for idx in pred_indices]
        
        # Return single prediction if single input
        if single_input:
            return predictions[0]
        
        return predictions
    
    def predict_proba(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        Predict class probabilities for input texts.
        
        Args:
            texts: Single text string or list of text strings
        
        Returns:
            Probability array [batch_size, num_classes]
        """
        # Handle single text input
        single_input = isinstance(texts, str)
        if single_input:
            texts = [texts]
        
        # Tokenize
        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="np"
        )
        
        # Prepare encoder inputs
        encoder_inputs = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64)
        }
        
        # Run encoder
        encoder_outputs = self.encoder_session.run(None, encoder_inputs)
        token_embeddings = encoder_outputs[0]
        
        # Apply mean pooling
        sentence_embeddings = self._mean_pooling(
            token_embeddings,
            inputs["attention_mask"]
        )
        
        # Run classifier
        classifier_inputs = {"float_input": sentence_embeddings.astype(np.float32)}
        classifier_outputs = self.classifier_session.run(None, classifier_inputs)
        
        # Get probabilities (second output from sklearn classifier)
        probabilities = classifier_outputs[1] if len(classifier_outputs) > 1 else None
        
        if probabilities is None:
            raise ValueError("Classifier does not output probabilities")
        
        # Return single prediction if single input
        if single_input:
            return probabilities[0]
        
        return probabilities


def demo():
    """Demo usage of the ONNX predictor"""
    
    # Example configuration
    ONNX_DIR = r"onnx_models/"
    
    # Initialize toxicity predictor
    print("\n" + "="*60)
    print("TOXICITY MODEL")
    print("="*60)
    toxicity_predictor = ONNXSetFitPredictor(
        encoder_path=os.path.join(ONNX_DIR, "toxicity_encoder_onnx"),
        classifier_path=os.path.join(ONNX_DIR, "toxicity_classifier.onnx"),
        labels_path=os.path.join(ONNX_DIR, "toxicity_labels.txt")
    )
    
    # Initialize emotion predictor
    print("\n" + "="*60)
    print("EMOTION MODEL")
    print("="*60)
    emotion_predictor = ONNXSetFitPredictor(
        encoder_path=os.path.join(ONNX_DIR, "emotion_encoder_onnx"),
        classifier_path=os.path.join(ONNX_DIR, "emotion_classifier.onnx"),
        labels_path=os.path.join(ONNX_DIR, "emotion_labels.txt")
    )

    # interaction type model 
    print("\n" + "="*60)
    print("INTERACTION TYPE MODEL")
    print("="*60)

    interaction_predictor = ONNXAutoModelClassifier(
        model_path=os.path.join(ONNX_DIR, "interaction_model_onnx", "model.onnx"),
        tokenizer_path=os.path.join(ONNX_DIR, "interaction_model_onnx"),
        labels=['technical_issue',
                    'performance_feedback',
                    'viewer_request',
                    'reaction',
                    'other']
        )

    
    # Test predictions
    test_texts = [
    "stream bi lag qua",
    "cho xin lai bai nhac vua roi",
    "camera bi mo",
    "hom nay stream vui qua",
    "am thanh bi nho",
    "cam on moi nguoi da xem",
    "cho xin ten game dang choi",
    "chat dang rat soi dong"
    ]
    
    print("\n" + "="*60)
    print("PREDICTIONS")
    print("="*60)
    
    toxicity_preds = toxicity_predictor.predict(test_texts)
    emotion_preds = emotion_predictor.predict(test_texts)
    interaction_preds = interaction_predictor.predict(test_texts)
    
    for i, text in enumerate(test_texts):
        print(f"\nText: '{text}'")
        print(f"  Toxicity: {toxicity_preds[i]}")
        print(f"  Emotion: {emotion_preds[i]}")
        print(f"  Interaction: {interaction_preds[i]}")


if __name__ == "__main__":
    demo()


