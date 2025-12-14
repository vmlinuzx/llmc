"""
HuggingFace Long-Context Adapter.
Handles loading and inference for models like Clinical-Longformer.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Any

log = logging.getLogger(__name__)

try:
    import torch
    from transformers import AutoModel, AutoTokenizer
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    log.warning("Transformers/Torch not installed. LongContextAdapter will fail if used.")


class LongContextAdapter:
    def __init__(self, config_path: Path):
        self.config = {}
        if config_path.exists():
            with open(config_path, "r") as f:
                self.config = json.load(f)
        
        self.model_name = self.config.get("model_name", "yikuan8/Clinical-Longformer")
        self.max_length = self.config.get("max_seq_tokens", 4096)
        self.device = "cuda" if HF_AVAILABLE and torch.cuda.is_available() else "cpu"
        
        self._model = None
        self._tokenizer = None

    def _load(self):
        if not HF_AVAILABLE:
            raise RuntimeError("HuggingFace dependencies not available.")
            
        if self._model is None:
            log.info(f"Loading {self.model_name} on {self.device}...")
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(
                self.model_name,
                trust_remote_code=self.config.get("trust_remote_code", False)
            ).to(self.device)
            self._model.eval()

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        """
        self._load()
        
        embeddings = []
        # Batch processing could be added here, doing simple loop for MVP
        for text in texts:
            inputs = self._tokenizer(
                text, 
                return_tensors="pt", 
                padding=True, 
                truncation=True, 
                max_length=self.max_length
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self._model(**inputs)
                # Mean pooling
                # Attention mask for correct averaging
                attention_mask = inputs['attention_mask']
                token_embeddings = outputs.last_hidden_state
                
                input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
                sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
                sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
                embedding = sum_embeddings / sum_mask
                
                # Normalize
                if self.config.get("normalize", True):
                    embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
                    
                embeddings.append(embedding[0].cpu().tolist())
                
        return embeddings
