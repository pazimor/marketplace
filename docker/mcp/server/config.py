import os


class Config:
    FALKORDB_HOST: str = os.getenv("FALKORDB_HOST", "127.0.0.1")
    FALKORDB_PORT: int = int(os.getenv("FALKORDB_PORT", "6379"))

    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "127.0.0.1")
    OLLAMA_PORT: int = int(os.getenv("OLLAMA_PORT", "11434"))

    CODE_EMBED_MODEL: str = os.getenv("CODE_EMBED_MODEL", "nomic-embed-text")
    MEMORY_EMBED_MODEL: str = os.getenv("MEMORY_EMBED_MODEL", "nomic-embed-text")

    MAX_DIM: int = int(os.getenv("MAX_DIM", "2048"))

    SERVER_PORT: int = int(os.getenv("MEM_PORT", "7333"))


config = Config()
