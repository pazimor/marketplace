import os


class Config:
    FALKORDB_HOST: str = os.getenv("FALKORDB_HOST", "127.0.0.1")
    FALKORDB_PORT: int = int(os.getenv("FALKORDB_PORT", "6379"))

    CODE_EMBED_MODEL: str = os.getenv("CODE_EMBED_MODEL", "microsoft/graphcodebert-base")
    MEMORY_EMBED_MODEL: str = os.getenv("MEMORY_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")

    MAX_DIM: int = int(os.getenv("MAX_DIM", "2048"))

    SERVER_PORT: int = int(os.getenv("MEM_PORT", "7333"))


config = Config()
