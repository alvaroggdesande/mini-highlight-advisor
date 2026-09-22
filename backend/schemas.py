from pydantic import BaseModel, Field


class PaintColorModel(BaseModel):
    name: str
    hex: str
    brand: str | None = None
    paint_range: str | None = None
    code: str = ""
    finish: str = "matte"


class WholeModel(BaseModel):
    palette: list[PaintColorModel]
    coverage: list[float]
    material: str = "matte"


class SettingsModel(BaseModel):
    edge_hl: bool = True
    edge_extreme: bool = False
    edge_sens: float = 0.5
    relief_cap: bool = True
    per_region_norm: bool = False


class AnalyzeRequest(BaseModel):
    photo_id: str
    whole: WholeModel
    settings: SettingsModel = Field(default_factory=SettingsModel)
