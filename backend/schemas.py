from pydantic import BaseModel, Field


class PaintColorModel(BaseModel):
    name: str
    hex: str
    brand: str | None = None
    paint_range: str | None = None
    code: str = ""
    finish: str = "matte"


class RegionModel(BaseModel):
    name: str
    rings: list[list[tuple[float, float]]]
    palette: list[PaintColorModel]
    coverage: list[float]
    material: str = "matte"


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
    regions: list[RegionModel] = Field(default_factory=list)


class RegionColorSpec(BaseModel):
    region_name: str
    surface: str
    tone: str | None = None
    n_bands: int
    is_anchor: bool = False


class SchemeGenerateRequest(BaseModel):
    specs: list[RegionColorSpec]
    anchor_name: str
    anchor_hex: str
    mood: str = "neutral"
    variant: str = "complementary"
    owned_codes: list[str] = Field(default_factory=list)


class RampGenerateRequest(BaseModel):
    midtone_hex: str = ""
    n: int
    variant: str = "ramp"
    blend_hexes: list[str] | None = None


class MatchRequest(BaseModel):
    hex: str
    finish: str = "matte"
    owned_codes: list[str] = Field(default_factory=list)


class RecipeStepModel(BaseModel):
    label: str
    hex: str
    paint_ref: str | None = None


class RecipeModel(BaseModel):
    name: str
    steps: list[RecipeStepModel]


class StepImageDto(BaseModel):
    index: int
    label: str
    kind: str  # "band" | "edge" | "shade"
    zone_png: str
    cumulative_png: str
    exact_png: str | None
    is_last: bool


class RegionPlanDto(BaseModel):
    name: str
    roles: list[str]
    coverage: list[float]
    steps: list[StepImageDto]


class StepsResponse(BaseModel):
    plans: list[RegionPlanDto]


class SaveProjectRequest(BaseModel):
    name: str
    active_angle: int = 0
    angles: list[dict] = Field(default_factory=list)
