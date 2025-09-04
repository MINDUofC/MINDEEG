from pathlib import Path
import os
import re
import gpt4all
from typing import Optional
import json
from rapidfuzz import process, fuzz


class ChatbotBE:

    def __init__(self):
        super().__init__()
        self.model_name = "Meta-Llama-3-8B-Instruct.Q4_0.gguf"
        self.model = gpt4all.GPT4All(self.model_name)
        self.chat_history = []
        # Separate controls for context size and generation length (tuned for average PCs)
        self.max_history_chars = 1200
        self.max_tokens = 192
        
        # Resolve paths relative to this file for robustness
        self.file_dir = Path(__file__).resolve().parent


        # Load FAQ data
        faq_path = self.file_dir / "faq.json"
        try:
            with open(faq_path, "r", encoding="utf-8") as f:
                self.faq_data = json.load(f)  # [{"q": "...", "a": "..."}]
        except Exception:
            self.faq_data = []

        # Pre-normalize questions for robust fuzzy matching
        self.questions = [self._normalize_text(item.get("q", "")) for item in self.faq_data]


        # Load system prompt (optional)
        system_prompt_path = self.file_dir / "SystemPrompt.txt"
        try:
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read().strip()
        except Exception:
            self.system_prompt = ""


        # FAQ fuzzy match configuration (stricter to avoid false positives)
        self.faq_threshold = 85
        self.faq_scorer = fuzz.token_set_ratio


    def handle_LLM_cycle(self, user_input: str) -> str:
        # TODO: Flow: User Input -> Add current chat history to user input -> Parse FAQs first for easy answers -> Handle LLM output if no FAQs found -> Update chat history -> Return LLM output
      
        faq_answer = self.parse_FAQ(user_input)

        if faq_answer: # If FAQ answer is found, update chat history and return FAQ answer
            self.update_chat_history(user_input, faq_answer)
            return faq_answer


        # Add current chat history to user input
        with self.model.chat_session():

            clean_up_user_input = self.clean_user_input(user_input)
            prompt = f"{self.system_prompt}\n\n{clean_up_user_input}".strip()

            LLM_output = self.model.generate(prompt, max_tokens=self.max_tokens)
            
        self.update_chat_history(user_input, LLM_output)
        

        return LLM_output

        

    def update_chat_history(self, user_input: str, LLM_FAQ_output: str):
        self.chat_history.append(f"USER: {user_input}")
        self.chat_history.append(f"ASSISTANT: {LLM_FAQ_output}")

    def parse_FAQ(self, user_input: str) -> Optional[str]:
        # Fuzzy match against FAQ with composite scoring
        query = self._normalize_text(user_input)
        prelim = process.extract(query, self.questions, scorer=fuzz.WRatio, limit=5)
        best_idx = None
        best_score = -1.0
        for choice, _score, idx in prelim:
            score = self._composite_score(query, choice)
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is not None and best_score >= self.faq_threshold:
            # Additional strictness: ensure reasonable token overlap and strong token_set score
            cand = self.questions[best_idx]
            overlap = self._token_overlap(query, cand)
            strong_token_set = fuzz.token_set_ratio(query, cand)
            if overlap >= 0.5 and strong_token_set >= (self.faq_threshold - 2):
                return self.faq_data[best_idx]["a"]
        return None


    def handle_new_conversation(self):
        self.chat_history = []


    def clean_user_input(self, user_input: str) -> str: 
        """
        Combine chat history with latest input while prioritizing the latest input.
        Truncates old history if necessary to fit max_length.
        """

        # Join history into one string (you can format however you like)
        historical_text = "\n".join(self.chat_history)

        # Ensure whitespace is normalized
        historical_text = " ".join(historical_text.split())
        user_input = " ".join(user_input.split())

        # Combine, with latest input clearly separated
        combined = f"{historical_text}\n\nLATEST USER INPUT: {user_input}"

        # If too long, truncate from the left (oldest first)
        if len(combined) > self.max_history_chars:
            overflow = len(combined) - self.max_history_chars
            historical_text = historical_text[overflow:]  # drop oldest chars
            combined = f"{historical_text}\n\nLATEST USER INPUT: {user_input}"

        return combined

    @staticmethod
    def _normalize_text(text: str) -> str:
        # Lowercase, strip punctuation (keep alphanumerics and spaces), collapse whitespace
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = " ".join(text.split())
        return text

    @staticmethod
    def _composite_score(a: str, b: str) -> float:
        # Blend multiple scorers; emphasize token_set for stricter matching
        s1 = fuzz.token_set_ratio(a, b)
        s2 = fuzz.partial_ratio(a, b)
        s3 = fuzz.QRatio(a, b)
        return 0.60 * s1 + 0.15 * s2 + 0.25 * s3

    @staticmethod
    def _token_overlap(a: str, b: str) -> float:
        a_tokens = set(a.split())
        b_tokens = set(b.split())
        if not a_tokens or not b_tokens:
            return 0.0
        inter = len(a_tokens & b_tokens)
        denom = max(1, min(len(a_tokens), len(b_tokens)))
        return inter / denom




    @staticmethod
    def is_model_installed(model_name: str = "Meta-Llama-3-8B-Instruct.Q4_0.gguf", model_path: Optional[str] = None) -> bool:
        """
        Returns True if the model file is already present locally according to GPT4All's
        resolution rules. This never triggers a download.

        - model_name: Either the filename (e.g., "Meta...gguf") or a full path
        - model_path: Optional directory where models are stored
        """
        try:
            # Construct with allow_download=False so it will error if not found locally
            _ = gpt4all.GPT4All(model_name, model_path=model_path, allow_download=False)
            return True
        except Exception:
            return False