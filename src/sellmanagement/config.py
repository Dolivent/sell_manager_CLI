from dataclasses import dataclass


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 4001
    client_id: int = 1
    dry_run: bool = True


