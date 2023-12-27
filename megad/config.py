from pydantic import BaseSettings


class Config(BaseSettings):
    interface: str = "0.0.0.0"  # ip адреса, который будет использоваться как адрес сервера для настройки обратной связи
    backup_path: str = "./mega_backups"


config = Config()
