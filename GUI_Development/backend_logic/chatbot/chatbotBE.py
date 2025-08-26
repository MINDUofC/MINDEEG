from gpt4all import GPT4All
from typing import Optional



class ChatbotBE:

    def __init__(self):
        super().__init__()
        self.model = gpt4all.GPT4All("Meta-Llama-3-8B-Instruct.Q4_0.gguf")




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