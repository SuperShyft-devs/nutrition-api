from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Tuple, List, Dict, Any
import uvicorn
import os

app = FastAPI(
    title="Metsights Nutrition Score API",
    description="Synchronized with Metsights Questionnaire Schema. Uses real key-value strings.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# SECRET KEY AUTHENTICATION
# ──────────────────────────────────────────────

# Set your secret key here or via environment variable: SECRET_KEY=your_key
SECRET_KEY = os.getenv("SECRET_KEY", "metsights-secret-2024")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != SECRET_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API key. Provide it via the 'X-API-Key' header.",
        )
    return api_key

# ──────────────────────────────────────────────
# CONFIGURATION & IDEAL RANGES
# ──────────────────────────────────────────────

IDEAL_RANGES = {
    "rarely": {"carbs": (45, 50), "fats": (25, 35), "protein": (15, 20), "fibre": (20, 25), "water_l": (2.0, 2.5)},
    "lt_1_hr": {"carbs": (45, 55), "fats": (20, 30), "protein": (15, 25), "fibre": (25, 30), "water_l": (2.0, 2.5)},
    "1_3_hr": {"carbs": (50, 55), "fats": (20, 30), "protein": (20, 30), "fibre": (25, 35), "water_l": (2.5, 3.0)},
    "4_8_hr": {"carbs": (50, 60), "fats": (20, 30), "protein": (25, 30), "fibre": (30, 40), "water_l": (3.0, 3.5)},
    "gt_8_hr": {"carbs": (55, 65), "fats": (20, 30), "protein": (25, 35), "fibre": (30, 45), "water_l": (3.5, 4.5)},
}

# ──────────────────────────────────────────────
# INTERNAL WEIGHT MAPPING
# Converts string keys from Questionnaire to original logic integers
# ──────────────────────────────────────────────

MAP_ACTIVITY = {"rarely": 0, "lt_1_hr": 1, "1_3_hr": 2, "4_8_hr": 3, "gt_8_hr": 4}
MAP_INTENSITY = {"low": 0, "moderate": 1, "high": 2}
MAP_BREAKFAST = {"none": 0, "lt_5": 1, "gt_5": 2}
MAP_DIET = {"veg": 0, "non_veg": 1, "eggetarian": 2, "pescatarian": 3, "flexitarian": 4, "jain": 5}
MAP_FREQUENCY_5 = {"rare": 0, "monthly": 1, "weekly_1": 2, "weekly_2_3": 3, "gt_4_week": 4}
MAP_FRUIT_VEG = {"rare": 0, "monthly": 1, "weekly_1": 2, "weekly_2_3": 3, "daily_1_2": 4}
MAP_COFFEE = {"none": 0, "0_1_day": 1, "1_2_day": 2, "gt_2_day": 2, "weekly": 1}
MAP_WATER = {"lt_2": 0, "2": 1, "4": 2, "6": 3, "8": 4, "gt_8": 5}
MAP_SMOKING = {"none": 0, "quit": 1, "1_3_week": 2, "5_7_week": 3, "gt_7_week": 4}
MAP_ALCOHOL = {"none": 0, "quit": 1, "3_per_week": 2, "gt_3_week": 3}
MAP_SICK = {"rare": 0, "1_2": 1, "2_3": 2, "4_5": 3, "gt_6": 4}

# ──────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────

class NutritionRequest(BaseModel):
    exercise_frequency_week: str = Field(..., description="Values: rarely, lt_1_hr, 1_3_hr, 4_8_hr, gt_8_hr")
    exercise_level: str = Field(..., description="Values: low, moderate, high")
    healthy_breakfast_frequency: str = Field(..., description="Values: none, lt_5, gt_5")
    diet_preference: str = Field(..., description="Values: veg, non_veg, eggetarian, pescatarian, flexitarian, jain")
    food_groups: List[str] = Field(..., description="List of strings like ['pulses', 'fruits']")
    fresh_fruit_frequency: str = Field(..., description="Values: rare, monthly, weekly_1, weekly_2_3, daily_1_2")
    fresh_vegetable_frequency: str = Field(..., description="Values: rare, monthly, weekly_1, weekly_2_3, daily_1_2")
    baked_goods_frequency: str = Field(..., description="Values: rare, monthly, weekly_1, weekly_2_3, gt_4_week")
    red_meat_frequency: str = Field(..., description="Values: rare, monthly, weekly_1, weekly_2_3, gt_4_week")
    butter_dish_frequency: str = Field(..., description="Values: rare, monthly, weekly_1, weekly_2_3, gt_4_week")
    dessert_frequency: str = Field(..., description="Values: rare, monthly, weekly_1, weekly_2_3, gt_4_week")
    caffeine_frequency: str = Field(..., description="Values: none, 0_1_day, 1_2_day, gt_2_day, weekly")
    water_intake_frequency: str = Field(..., description="Values: lt_2, 2, 4, 6, 8, gt_8")
    tobacco_frequency: str = Field(..., description="Values: none, quit, 1_3_week, 5_7_week, gt_7_week")
    alcohol_frequency: str = Field(..., description="Values: none, quit, 3_per_week, gt_3_week")
    sickness_frequency: str = Field(..., description="Values: rare, 1_2, 2_3, 4_5, gt_6")

class RangeValue(BaseModel):
    estimated_low: float
    estimated_high: float
    ideal_low: float
    ideal_high: float
    status: str

class WaterValue(BaseModel):
    estimated_litres: float
    ideal_low_litres: float
    ideal_high_litres: float
    status: str

class NutritionResponse(BaseModel):
    nutrition_score: int
    risk_band: str
    carbs: RangeValue
    fats: RangeValue
    protein: RangeValue
    fibre: RangeValue
    water: WaterValue

# ──────────────────────────────────────────────
# CALCULATION LOGIC (ADAPTED)
# ──────────────────────────────────────────────

def _status(est_low, est_high, ideal_low, ideal_high) -> str:
    if est_low > ideal_high: return "above_ideal"
    if est_high < ideal_low: return "below_ideal"
    return "within_ideal"

@app.post("/calculate", response_model=NutritionResponse, dependencies=[Depends(verify_api_key)])
def calculate_nutrition(p: NutritionRequest):
    try:
        # 1. Convert Strings to Logic Values
        act_val = MAP_ACTIVITY[p.exercise_frequency_week]
        int_val = MAP_INTENSITY[p.exercise_level]
        brk_val = MAP_BREAKFAST[p.healthy_breakfast_frequency]
        diet_val = MAP_DIET[p.diet_preference]
        
        # Food groups logic: count total selections (capped at 3 for logic compatibility)
        fg_count = len(p.food_groups)
        fg_val = 0 if fg_count == 0 else 1 if fg_count <= 3 else 2 if fg_count <= 6 else 3
        
        fruit_val = MAP_FRUIT_VEG[p.fresh_fruit_frequency]
        veg_val = MAP_FRUIT_VEG[p.fresh_vegetable_frequency]
        cookie_val = MAP_FREQUENCY_5[p.baked_goods_frequency]
        meat_val = MAP_FREQUENCY_5[p.red_meat_frequency]
        butter_val = MAP_FREQUENCY_5[p.butter_dish_frequency]
        sugar_val = MAP_FREQUENCY_5[p.dessert_frequency]
        coff_val = MAP_COFFEE[p.caffeine_frequency]
        wat_idx = MAP_WATER[p.water_intake_frequency]
        smoke_val = MAP_SMOKING[p.tobacco_frequency]
        alc_val = MAP_ALCOHOL[p.alcohol_frequency]
        sick_val = MAP_SICK[p.sickness_frequency]

        ideal = IDEAL_RANGES[p.exercise_frequency_week]

        # 2. Mathematical Calculations (Preserved from main.py)
        # Carbs
        c_base = (ideal["carbs"][0] + ideal["carbs"][1]) / 2
        c_est = c_base + {0:-4, 1:-1, 2:0}[brk_val] + {0:-3, 1:-1, 2:1, 3:3, 4:6}[cookie_val] + {0:-3, 1:-1, 2:1, 3:3, 4:6}[sugar_val]
        
        # Fats
        f_base = (ideal["fats"][0] + ideal["fats"][1]) / 2
        f_est = f_base + {0:-2, 1:3, 2:1, 3:1, 4:2, 5:-3}[diet_val] + {0:-2, 1:0, 2:1, 3:3, 4:5}[meat_val] + {0:-2, 1:0, 2:1, 3:3, 4:5}[butter_val]
        
        # Protein
        p_base = (ideal["protein"][0] + ideal["protein"][1]) / 2
        p_est = p_base + {0:-2, 1:0, 2:3}[int_val] + {0:-2, 1:4, 2:2, 3:3, 4:2, 5:-3}[diet_val] + {0:-3, 1:-1, 2:1, 3:2}[fg_val]

        # Fibre
        fib_base = (ideal["fibre"][0] + ideal["fibre"][1]) / 2
        fib_est = max(5, min(60, fib_base + {0:-8, 1:-4, 2:2, 3:5}[fg_val] + {0:-6, 1:-3, 2:0, 3:3, 4:6}[fruit_val] + {0:-6, 1:-3, 2:0, 3:3, 4:7}[veg_val]))

        # Water
        wat_litres = {0:0.25, 1:0.5, 2:1.0, 3:1.5, 4:2.0, 5:2.5}[wat_idx] # Simple conversion

        # 3. Nutrition Score (Inverted Logic)
        score_base = 50
        adj = (
            {0:0, 1:-4, 2:-8}[brk_val] + {0:0, 1:-4, 2:-8, 3:-12}[fg_val] + 
            {0:0, 1:-2, 2:-4, 3:-7, 4:-10}[fruit_val] + {0:0, 1:-2, 2:-5, 3:-8, 4:-12}[veg_val] +
            {0:0, 1:-1, 2:-3, 3:-5, 4:-8, 5:-6}[wat_idx] + {0:0, 1:2, 2:4, 3:7, 4:10}[cookie_val] +
            {0:0, 1:1, 2:3, 3:6, 4:8}[meat_val] + {0:0, 1:1, 2:3, 3:6, 4:8}[butter_val] +
            {0:0, 1:2, 2:5, 3:8, 4:12}[sugar_val] + {0:0, 1:1, 2:4}[coff_val] +
            {0:0, 1:-2, 2:5, 3:10, 4:15}[smoke_val] + {0:0, 1:-2, 2:5, 3:10}[alc_val] + {0:0, 1:2, 2:4, 3:6, 4:8}[sick_val]
        )
        final_score = 100 - max(0, min(100, round(score_base + adj)))

        return NutritionResponse(
            nutrition_score=final_score,
            risk_band="Healthy" if final_score >= 76 else "Increased Risk" if final_score >= 51 else "High Risk" if final_score >= 26 else "Very High Risk",
            carbs=RangeValue(estimated_low=round(c_est-2,1), estimated_high=round(c_est+2,1), ideal_low=ideal["carbs"][0], ideal_high=ideal["carbs"][1], status=_status(c_est-2, c_est+2, *ideal["carbs"])),
            fats=RangeValue(estimated_low=round(f_est-2,1), estimated_high=round(f_est+2,1), ideal_low=ideal["fats"][0], ideal_high=ideal["fats"][1], status=_status(f_est-2, f_est+2, *ideal["fats"])),
            protein=RangeValue(estimated_low=round(p_est-2,1), estimated_high=round(p_est+2,1), ideal_low=ideal["protein"][0], ideal_high=ideal["protein"][1], status=_status(p_est-2, p_est+2, *ideal["protein"])),
            fibre=RangeValue(estimated_low=round(fib_est-2,1), estimated_high=round(fib_est+2,1), ideal_low=ideal["fibre"][0], ideal_high=ideal["fibre"][1], status=_status(fib_est-2, fib_est+2, *ideal["fibre"])),
            water=WaterValue(estimated_litres=wat_litres, ideal_low_litres=ideal["water_l"][0], ideal_high_litres=ideal["water_l"][1], status="within_ideal" if ideal["water_l"][0] <= wat_litres <= ideal["water_l"][1] else "below_ideal" if wat_litres < ideal["water_l"][0] else "above_ideal")
        )
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Invalid option key provided: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
