from dataclasses import dataclass


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 4001
    client_id: int = 1
    dry_run: bool = True
    # download manager settings
    download_workers: int = 2
    download_concurrency: int = 4
    batch_size: int = 32
    batch_delay: float = 6.0


