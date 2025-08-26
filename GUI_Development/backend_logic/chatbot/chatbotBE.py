from gpt4all import GPT4All
from typing import Optional
import json
from rapidfuzz import process, fuzz


class ChatbotBE:

    def __init__(self):
        super().__init__()
        self.model = gpt4all.GPT4All("Meta-Llama-3-8B-Instruct.Q4_0.gguf")
        self.chat_history = []
        self.max_length = 1024

        with open("faq.json", "r", encoding="utf-8") as f:
            self.faq_data = json.load(f)  # [{"q": "...", "a": "..."}]

        self.questions = [item["q"] for item in self.faq_data]


    def handle_LLM_cycle(self, user_input: str) -> str:
        # TODO: Flow: User Input -> Add current chat history to user input -> Parse FAQs first for easy answers -> Handle LLM output if no FAQs found -> Update chat history -> Return LLM output
      
        faq_answer = self.parse_FAQ(user_input)

        if faq_answer: # If FAQ answer is found, update chat history and return FAQ answer
            self.update_chat_history(user_input, faq_answer)
            return faq_answer


        # Add current chat history to user input
        with self.model.chat_session():

            clean_up_user_input = self.clean_user_input(user_input)

            LLM_output = self.model.generate(clean_up_user_input, max_tokens=self.max_length)
            
        self.update_chat_history(user_input, LLM_output)
        

        return LLM_output

        

    def update_chat_history(self, user_input: str, LLM_FAQ_output: str):
        self.chat_history.append(f"USER: {user_input}")
        self.chat_history.append(f"ASSISTANT: {LLM_FAQ_output}")

    def parse_FAQ(self, user_input: str) -> str:
        # Fuzzy match against FAQ
        best = process.extractOne(user_input, self.questions, scorer=fuzz.token_sort_ratio)

        if best and (best[1] >= threshold):
            match_idx = self.questions.index(best[0])
            return self.faq_data[match_idx]["a"]
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
        if len(combined) > self.max_length:
            overflow = len(combined) - self.max_length
            historical_text = historical_text[overflow:]  # drop oldest chars
            combined = f"{historical_text}\n\nLATEST USER INPUT: {user_input}"

        return combined




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