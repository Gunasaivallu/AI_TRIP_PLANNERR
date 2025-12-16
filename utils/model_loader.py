import os
from dotenv import load_dotenv
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field
from utils.config_loader import load_config
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

# Ensure .env is loaded
load_dotenv()

DECOMMISSIONED = {
    "deepseek-r1-distill-llama-70b",
    "deepseek-r1-distill-llama-70b-q4_k_m",  # if you ever used a quant variant
}

# Safe, currently supported Groq defaults
GROQ_DEFAULT = "llama-3.1-8b-instant"
GROQ_ALLOWED_FALLBACKS = [
    "llama-3.1-70b-versatile",
    "llama-3.2-90b-text-preview",
    "mixtral-8x7b",
]

class ConfigLoader:
    def __init__(self):
        print("Loaded config.....")
        self.config = load_config()
    
    def __getitem__(self, key):
        return self.config[key]

class ModelLoader(BaseModel):
    model_provider: Literal["groq"] = "groq"
    config: Optional[ConfigLoader] = Field(default=None, exclude=True)

    def model_post_init(self, __context: Any) -> None:
        self.config = ConfigLoader()
    
    class Config:
        arbitrary_types_allowed = True
    
    def _resolve_groq_model(self) -> str:
        """
        Decide the Groq model with this priority:
        1) env GROQ_MODEL
        2) config['llm']['groq']['model_name']
        3) safe default
        Also guard against decommissioned models.
        """
        env_model = os.getenv("GROQ_MODEL")
        cfg_model = None
        try:
            cfg_model = self.config["llm"]["groq"]["model_name"]
        except Exception:
            pass

        model_name = (env_model or cfg_model or GROQ_DEFAULT).strip()

        if model_name in DECOMMISSIONED:
            print(f"[warn] '{model_name}' is decommissioned. Falling back to '{GROQ_DEFAULT}'.")
            model_name = GROQ_DEFAULT

        return model_name

    def load_llm(self):
        """
        Load and return the LLM model.
        """
        print("LLM loading...")
        print(f"Loading model from provider: {self.model_provider}")

        if self.model_provider == "groq":
            print("Loading LLM from Groq..............")
            groq_api_key = os.getenv("GROQ_API_KEY")
            if not groq_api_key:
                raise RuntimeError("GROQ_API_KEY is not set")

            model_name = self._resolve_groq_model()
            if model_name not in {GROQ_DEFAULT, *GROQ_ALLOWED_FALLBACKS}:
                print(f"[info] Using custom GROQ model: {model_name}")

            # LangChain Groq chat model
            llm = ChatGroq(
                model=model_name,          # <- use model= for ChatGroq
                api_key=groq_api_key,
                temperature=0.2,
                timeout=60,
            )
            return llm

        elif self.model_provider == "openai":
            print("Loading LLM from OpenAI..............")
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is not set")

            # Prefer env override; else config; else a sensible default
            model_name = os.getenv("OPENAI_MODEL")
            if not model_name:
                try:
                    model_name = self.config["llm"]["openai"]["model_name"]
                except Exception:
                    model_name = "gpt-4o-mini"  # safe default alias

            llm = ChatOpenAI(
                model=model_name,
                api_key=openai_api_key,
                temperature=0.2,
                timeout=60,
            )
            return llm

        else:
            raise ValueError(f"Unsupported model_provider: {self.model_provider}")
