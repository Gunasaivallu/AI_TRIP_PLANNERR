import os
from dotenv import load_dotenv
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field
from utils.config_loader import load_config
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv()

# Decommissioned / unsafe models
DECOMMISSIONED = {
    "deepseek-r1-distill-llama-70b",
    "deepseek-r1-distill-llama-70b-q4_k_m",
}

# Safe Groq defaults
GROQ_DEFAULT = "llama-3.1-8b-instant"
GROQ_ALLOWED_FALLBACKS = {
    "llama-3.1-70b-versatile",
    "llama-3.2-90b-text-preview",
    "mixtral-8x7b",
}

class ConfigLoader:
    def __init__(self):
        print("Loaded config.....")
        self.config = load_config()

    def __getitem__(self, key):
        return self.config[key]

class ModelLoader(BaseModel):
    model_provider: Literal["groq"] = "groq"
    config: Optional[ConfigLoader] = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self, __context: Any) -> None:
        self.config = ConfigLoader()

    def _resolve_groq_model(self) -> str:
        """
        Model priority:
        1. GROQ_MODEL env var
        2. config['llm']['groq']['model_name']
        3. safe default
        """
        env_model = os.getenv("GROQ_MODEL")
        cfg_model = None

        try:
            cfg_model = self.config["llm"]["groq"]["model_name"]
        except Exception:
            pass

        model_name = (env_model or cfg_model or GROQ_DEFAULT).strip()

        if model_name in DECOMMISSIONED:
            print(
                f"[WARN] '{model_name}' is decommissioned. "
                f"Falling back to '{GROQ_DEFAULT}'."
            )
            model_name = GROQ_DEFAULT

        return model_name

    def load_llm(self):
        """
        Load Groq LLM using LangChain ChatGroq
        """
        print("LLM loading...")
        print("Provider: Groq")

        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise RuntimeError("❌ GROQ_API_KEY is not set in environment")

        model_name = self._resolve_groq_model()

        if model_name not in {GROQ_DEFAULT, *GROQ_ALLOWED_FALLBACKS}:
            print(f"[INFO] Using custom Groq model: {model_name}")

        return ChatGroq(
            model=model_name,
            api_key=groq_api_key,
            temperature=0.2,
            timeout=60,
        )
