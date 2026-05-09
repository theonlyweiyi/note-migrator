from pydantic import BaseModel, Field
from typing import Optional


class XiaomiAuth(BaseModel):
    service_token: str = ""
    user_id: str = ""
    pass_token: str = ""


class XiaomiConfig(BaseModel):
    auth: XiaomiAuth = Field(default_factory=XiaomiAuth)
    base_url: str = "https://i.mi.com"
    request_timeout: int = 30
    max_retries: int = 3


class VivoConfig(BaseModel):
    base_url: str = "https://pc.vivo.com"
    session_file: str = "output/vivo_session.json"
    headless: bool = False
    typing_delay_ms: int = 100
    max_retries: int = 3


class ExportConfig(BaseModel):
    output_dir: str = "output"
    concurrency: int = 3
    include_archived: bool = False
    date_format: str = "%Y-%m-%d %H:%M"


class ImportConfig(BaseModel):
    checkpoint_file: str = "output/import_checkpoint.json"
    delay_between_notes: float = 2.0
    max_retries_per_note: int = 3


class AppConfig(BaseModel):
    xiaomi: XiaomiConfig = Field(default_factory=XiaomiConfig)
    vivo: VivoConfig = Field(default_factory=VivoConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    import_cfg: ImportConfig = Field(default_factory=ImportConfig, alias="import")
