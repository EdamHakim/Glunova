import os
import time
import json
import base64
from pathlib import Path
import re
import requests
from typing import List, Dict, Any, Optional
from PIL import Image as PILImage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Utilities ---

def call_with_retry(fn, max_retries=3, delay=2):
    """Retry an API call with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = delay * (2 ** attempt)
            print(f"  ⚠️  Attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)

def validate_nutrition_response(data: dict) -> dict:
    """Validates the structure of the JSON returned by the LLM."""
    required_keys = ["summary", "dish_type", "ingredients_analysis", 
                     "global_assessment", "recommendations", "healthy_alternatives"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing key in nutrition response: '{key}'")
    assessment = data["global_assessment"]
    for k in ["total_calories", "total_glycemic_load", "risk_level", "explanation"]:
        if k not in assessment:
            raise ValueError(f"Missing key in global_assessment: '{k}'")
    return data

# --- YOLO-World Configuration ---

SYNONYMES = {
    "cheese"    : ["mozzarella", "cheddar", "feta", "parmesan", "cheese slice"],
    "avocado"   : ["avocado half", "green spread", "guacamole"],
    "chicken"   : ["chicken breast", "grilled chicken", "poultry", "meat"],
    "beef"      : ["ground beef", "steak", "meat patty"],
    "fish"      : ["salmon", "tuna", "grilled fish", "fish fillet"],
    "sauce"     : ["tomato sauce", "white sauce", "dressing"],
    "lettuce"   : ["salad leaves", "green leaves", "romaine", "spinach"],
    "onion"     : ["sliced onion", "caramelized onion", "spring onion"],
    "pepper"    : ["bell pepper", "red pepper", "green pepper"],
    "mushroom"  : ["sliced mushroom", "champignon"],
    "potato"    : ["french fries", "mashed potato", "roasted potato"],
    "pasta"     : ["spaghetti", "penne", "noodles"],
    "rice"      : ["white rice", "cooked rice"],
    "bread"     : ["toast", "baguette", "pita", "bun"],
    "egg"       : ["fried egg", "boiled egg", "scrambled egg"],
    "tomato"    : ["cherry tomato", "sliced tomato", "tomato wedge"],
    "cucumber"  : ["sliced cucumber", "cucumber stick"],
    "carrot"    : ["sliced carrot", "grated carrot"],
    "lamb"      : ["lamb chop", "grilled lamb", "mutton"],
    "merguez"   : ["sausage", "lamb sausage", "spicy sausage"],
    "couscous"  : ["semolina", "grain"],
    "chickpea"  : ["cooked chickpea", "garbanzo bean"],
    "lentil"    : ["cooked lentil", "red lentil"],
    "olive"     : ["black olive", "green olive"],
    "ham"       : ["cured ham", "deli meat", "prosciutto"],
    "bacon"     : ["crispy bacon", "bacon strip"],
    "shrimp"    : ["prawn", "cooked shrimp"],
    "yogurt"    : ["greek yogurt", "white cream"],
}


def _resolve_yolo_weights_path() -> str:
    """
    Ultralytics downloads ~330MB from the hub if the path string is not an existing file.
    A bare env value like YOLO_MODEL=yolov8s-worldv2.pt is resolved against cwd, not
    nutrition/models/, so we fall back to the bundled weights next to this package.
    """
    _pkg = Path(__file__).resolve().parent
    _models_dir = _pkg / "models"
    _default = _models_dir / "yolov8s-worldv2.pt"
    raw = (os.environ.get("YOLO_MODEL") or "").strip()
    if not raw:
        return str(_default)
    candidate = Path(raw).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    # Same filename / relative path under bundled models/ (typical .env mistake)
    next_to_pkg = (_models_dir / candidate.name)
    if next_to_pkg.is_file():
        if raw != str(next_to_pkg.resolve()):
            print(
                f"  ℹ️  YOLO_MODEL={raw!r} is not a file on disk; using bundled weights at {next_to_pkg}"
            )
        return str(next_to_pkg.resolve())
    if _default.is_file():
        print(
            f"  ⚠️  YOLO_MODEL={raw!r} not found; using default {_default}. "
            "Unset YOLO_MODEL or set it to an absolute path to avoid duplicate downloads."
        )
        return str(_default.resolve())
    return str(candidate)


def _nutrition_yolo_backend() -> str:
    """ultralytics | roboflow | groq_only — see PipelineNutrition docstring."""
    raw = (os.environ.get("NUTRITION_YOLO_BACKEND") or os.environ.get("YOLO_WORLD_BACKEND") or "ultralytics").strip().lower()
    if raw in ("local", "ultralytics", "yolo", ""):
        return "ultralytics"
    if raw in ("roboflow", "serverless", "remote", "inference"):
        return "roboflow"
    if raw in ("groq_only", "groq", "vision_only", "skip_yolo"):
        return "groq_only"
    raise ValueError(
        f"Unknown NUTRITION_YOLO_BACKEND={raw!r}. Use ultralytics, roboflow, or groq_only."
    )


def _parse_roboflow_yolo_world(result: dict, vocab: list[str]) -> list[dict]:
    """Map Roboflow /yolo_world/infer JSON to the same list shape as local YOLO."""
    out: list[dict] = []
    for p in result.get("predictions") or []:
        try:
            x = float(p["x"])
            y = float(p["y"])
            w = float(p["width"])
            h = float(p["height"])
        except (KeyError, TypeError, ValueError):
            continue
        x1, y1 = int(x - w / 2), int(y - h / 2)
        x2, y2 = int(x1 + w), int(y1 + h)
        idx = int(p.get("class_id", -1))
        if 0 <= idx < len(vocab):
            label = vocab[idx]
        else:
            label = str(p.get("class", "")).strip()
        if not label:
            continue
        conf = round(float(p.get("confidence", 0.0)), 3)
        out.append({"ingredient": label, "confiance": conf, "bbox": [x1, y1, x2, y2]})
    return out


class PipelineNutrition:
    """Nutrition pipeline; see ``NUTRITION_YOLO_BACKEND`` (ultralytics | roboflow | groq_only)."""

    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key or os.environ.get("GROQ_API_KEY")
        if not self.groq_api_key:
            raise EnvironmentError("GROQ_API_KEY is not set. Add it to your .env file.")

        self._yolo_backend = _nutrition_yolo_backend()
        self.yolo_model = None
        self._rf_client = None
        self._rf_yolo_version = (os.environ.get("ROBOFLOW_YOLO_WORLD_VERSION") or "v2-s").strip()

        if self._yolo_backend == "roboflow":
            from inference_sdk import InferenceHTTPClient

            rf_key = (os.environ.get("ROBOFLOW_API_KEY") or "").strip()
            if not rf_key:
                raise EnvironmentError(
                    "NUTRITION_YOLO_BACKEND=roboflow requires ROBOFLOW_API_KEY in the environment."
                )
            api_url = (os.environ.get("ROBOFLOW_SERVERLESS_URL") or "https://serverless.roboflow.com").strip().rstrip("/")
            self._rf_client = InferenceHTTPClient(api_url=api_url, api_key=rf_key)
            print(f"✅ YOLO-World via Roboflow serverless ({api_url}, model={self._rf_yolo_version!r}) — no local CLIP download.")
        elif self._yolo_backend == "groq_only":
            print("✅ Nutrition YOLO: groq_only (no local YOLO/CLIP).")
        else:
            from ultralytics import YOLOWorld

            print("Chargement de YOLO-World (Ultralytics)…")
            print("  ℹ️  First detection will download CLIP ViT-B/32 (~338MB) once; use NUTRITION_YOLO_BACKEND=roboflow or groq_only to skip.")
            yolo_model_path = _resolve_yolo_weights_path()
            self.yolo_model = YOLOWorld(yolo_model_path)
            self.yolo_model.to("cpu")
            print("✅ YOLO-World chargé (local weights + CLIP on first set_classes).")

    def _charger_image_base64(self, image_path: str) -> tuple:
        if image_path.startswith("http"):
            response = requests.get(image_path, timeout=10)
            response.raise_for_status()
            image_bytes = response.content
            content_type = response.headers.get("Content-Type", "image/jpeg")
            media_type = content_type.split(";")[0].strip()
        else:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            ext = image_path.lower().split(".")[-1]
            media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                          "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")

        image_base64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        return image_base64, media_type

    def identifier_ingredients_groq(self, image_path: str) -> dict:
        image_base64, media_type = self._charger_image_base64(image_path)

        prompt = """
You are an expert in nutrition and Mediterranean/Maghreb cuisine.

Analyze this food image and return ONLY a valid JSON object.
No text before or after. No markdown. No ```json fences.

Required format:
{
    "dish": "name of the dish",
    "ingredients": ["ingredient1", "ingredient2", "ingredient3"],
    "confidence": "high|medium|low"
}

Instructions:
- Ingredients MUST be in English
- Use simple, common object names (e.g., "bread", "chicken", "rice", "egg", "cup")
- Prefer visually detectable objects
- Maximum 15 ingredients, minimum 3
- Include visible and likely ingredients
"""

        def api_call():
            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{image_base64}"}
                            },
                            {"type": "text", "text": prompt}
                        ]
                    }
                ],
                "max_tokens": 1024
            }
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()

        response_json = call_with_retry(api_call)
        raw_text = response_json["choices"][0]["message"]["content"].strip()
        raw_text = re.sub(r'```json\s*|```\s*', '', raw_text).strip()
        return json.loads(raw_text)

    def _predict_once(self, image_path: str, vocab: list, seuil: float) -> list:
        if not vocab:
            return []
        if self._yolo_backend == "groq_only":
            return []
        if self._yolo_backend == "roboflow" and self._rf_client is not None:
            raw_list = self._rf_client.infer_from_yolo_world(
                inference_input=image_path,
                class_names=vocab,
                model_version=self._rf_yolo_version,
                confidence=seuil,
            )
            raw = raw_list[0] if raw_list else {}
            return _parse_roboflow_yolo_world(raw, vocab)
        if self.yolo_model is None:
            return []
        self.yolo_model.set_classes(vocab)
        rs = self.yolo_model.predict(image_path, conf=seuil, verbose=False, device="cpu")
        out = []
        for r in rs:
            for box in r.boxes:
                idx = int(box.cls[0].item())
                if idx >= len(vocab):
                    continue
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                out.append({
                    "ingredient": vocab[idx],
                    "confiance" : round(float(box.conf[0].item()), 3),
                    "bbox"      : [x1, y1, x2, y2]
                })
        return out

    def detecter_ingredients_yolo(self, image_path: str, ingredients: list, seuil_confiance: float = 0.20) -> list:
        ingredients = [str(i).strip() for i in ingredients if str(i).strip()]
        if not ingredients:
            return []

        if self._yolo_backend == "groq_only":
            return [
                {
                    "ingredient": ing,
                    "confiance": 0.0,
                    "bbox": [0, 0, 0, 0],
                    "detecte_par": "groq_vision_only",
                }
                for ing in ingredients
            ]

        # Passe 1
        dets_p1 = self._predict_once(image_path, ingredients, seuil_confiance)
        trouves = {d["ingredient"].lower() for d in dets_p1}
        manquants = [ing for ing in ingredients if ing.lower() not in trouves]

        # Passe 2
        dets_p2 = []
        for ing in manquants:
            syns = SYNONYMES.get(ing.lower(), [])
            if not syns: continue
            dets_s = self._predict_once(image_path, syns, seuil_confiance)
            if dets_s:
                best = max(dets_s, key=lambda x: x["confiance"])
                best["ingredient"] = ing
                dets_p2.append(best)

        all_dets = dets_p1 + dets_p2
        all_dets.sort(key=lambda x: x["confiance"], reverse=True)

        # Passe 3 Fallback
        trouves_final = {d["ingredient"].lower() for d in all_dets}
        encore_manquants = [ing for ing in ingredients if ing.lower() not in trouves_final]
        for ing in encore_manquants:
            all_dets.append({
                "ingredient" : ing,
                "confiance"  : 0.0,
                "bbox"       : [0, 0, 0, 0],
                "surface_px" : 0,
                "surface_pct": 0.0,
                "masque"     : None,
                "detecte_par": "groq_vision_only"
            })

        return all_dets

    def segmenter_ingredients_sam(self, image_path: str, detections: list) -> list:
        """
        Improved portion size estimation from YOLO bounding boxes.
        1. Uses elliptical approximation (pi/4) for realistic food shapes.
        2. Calculates plate-relative surface percentage if a plate/bowl is detected.
        """
        img = PILImage.open(image_path)
        total_area = img.width * img.height
        
        # Elliptical factor (pi/4) - most food items aren't perfect rectangles
        ELLIPSE_FACTOR = 0.785 

        # Find a reference container (plate, bowl, etc.)
        container_keywords = ["plate", "bowl", "dish", "container", "assiette", "bol"]
        reference_container = None
        for det in detections:
            if any(kw in det["ingredient"].lower() for kw in container_keywords) and det["bbox"] != [0, 0, 0, 0]:
                if not reference_container or (det["bbox"][2]-det["bbox"][0]) * (det["bbox"][3]-det["bbox"][1]) > \
                   (reference_container["bbox"][2]-reference_container["bbox"][0]) * (reference_container["bbox"][3]-reference_container["bbox"][1]):
                    reference_container = det

        results = []
        for det in detections:
            if det.get("detecte_par") == "groq_vision_only" or det["bbox"] == [0, 0, 0, 0]:
                results.append({**det, "masque": None, "surface_px": 0, "surface_pct": 0.0, "plate_coverage_pct": 0.0})
                continue

            x1, y1, x2, y2 = det["bbox"]
            width = x2 - x1
            height = y2 - y1
            
            # Use elliptical approximation for area
            estimated_area = width * height * ELLIPSE_FACTOR
            
            surface_pct = round((estimated_area / total_area) * 100, 2) if total_area else 0.0
            
            # Calculate plate-relative coverage
            plate_coverage_pct = 0.0
            if reference_container and det != reference_container:
                rx1, ry1, rx2, ry2 = reference_container["bbox"]
                ref_area = (rx2 - rx1) * (ry2 - ry1) * ELLIPSE_FACTOR
                if ref_area > 0:
                    plate_coverage_pct = round((estimated_area / ref_area) * 100, 2)

            results.append({
                **det,
                "masque": None,
                "surface_px": int(estimated_area),
                "surface_pct": surface_pct,
                "plate_coverage_pct": plate_coverage_pct
            })

        return results

    def analyser_nutrition_groq(self, dish_name: str, ingredients_data: list, profil: dict) -> dict:
        prompt = f"""
You are an expert clinical nutritionist specialized in diabetes.
Analyze this meal for a patient with the following profile:
{json.dumps(profil, indent=2)}

Meal identified: {dish_name}
Ingredients detected (with visual surface coverage):
{json.dumps([{ 'ing': d['ingredient'], 'surf_image_pct': d['surface_pct'], 'surf_plate_pct': d.get('plate_coverage_pct', 0) } for d in ingredients_data], indent=2)}

Return a valid JSON object (NO text before/after, NO markdown) with this structure:
{{
  "summary": "1-2 sentence description",
  "dish_type": "category of dish",
  "ingredients_analysis": [
    {{ "ingredient": "name", "gi": "low|medium|high", "benefit": "...", "risk_for_diabetic": "..." }}
  ],
  "global_assessment": {{
    "total_calories": "approx kcal",
    "total_glycemic_load": "low|medium|high",
    "risk_level": "green|orange|red",
    "explanation": "why this risk level for this profile"
  }},
  "recommendations": ["advice 1", "advice 2", "advice 3"],
  "healthy_alternatives": [
    {{ "replace": "...", "with": "...", "benefit": "..." }}
  ]
}}
"""
        def api_call():
            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2048
            }
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()

        response_json = call_with_retry(api_call)
        raw_text = response_json["choices"][0]["message"]["content"].strip()
        raw_text = re.sub(r'```json\s*|```\s*', '', raw_text).strip()
        
        data = json.loads(raw_text)
        return validate_nutrition_response(data)

    def analyser(self, image_path: str, profil: dict, return_masks: bool = False) -> dict:
        start_time = time.time()
        
        # 1. Groq Vision
        print(f"Step 1/4: Groq Vision...")
        vision_res = self.identifier_ingredients_groq(image_path)
        
        # 2. YOLO-World
        print(f"Step 2/4: YOLO-World...")
        detections = self.detecter_ingredients_yolo(image_path, vision_res["ingredients"])

        detections_final = self.segmenter_ingredients_sam(image_path, detections)
        
        # 3. Nutrition Analysis
        print(f"Step 3/3: Nutrition Analysis...")
        nutrition_res = self.analyser_nutrition_groq(vision_res["dish"], detections_final, profil)
        
        # Clean results for serialisation
        clean_ingredients = []
        for d in detections_final:
            clean_ingredients.append({
                "ingredient": d["ingredient"],
                "confiance_visuelle": d["confiance"],
                "surface_pct": d["surface_pct"],
                "plate_coverage_pct": d.get("plate_coverage_pct", 0)
            })

        rapport = {
            "plat_identifie": vision_res["dish"],
            "confiance_identification": vision_res["confidence"],
            "ingredients_detectes": clean_ingredients,
            "analyse_nutritionnelle": nutrition_res,
            "profil_patient": profil,
            "temps_traitement_sec": round(time.time() - start_time, 2)
        }
        
        return rapport
