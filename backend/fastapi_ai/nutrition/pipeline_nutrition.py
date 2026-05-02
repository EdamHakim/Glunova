import os
import time
import json
import base64
import re
import requests
import numpy as np
import cv2
from typing import List, Dict, Any, Optional
from PIL import Image as PILImage
from ultralytics import YOLOWorld
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

class PipelineNutrition:
    def __init__(self, groq_api_key: Optional[str] = None, roboflow_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key or os.environ.get("GROQ_API_KEY")
        if not self.groq_api_key:
            raise EnvironmentError("GROQ_API_KEY is not set. Add it to your .env file.")
        
        self.roboflow_api_key = roboflow_api_key or os.environ.get("ROBOFLOW_API_KEY")
        if not self.roboflow_api_key:
            raise EnvironmentError("ROBOFLOW_API_KEY is not set. Add it to your .env file.")

        print("Chargement de YOLO-World...")
        yolo_model_path = os.environ.get("YOLO_MODEL", "yolov8s-worldv2.pt")
        self.yolo_model = YOLOWorld(yolo_model_path)
        # YOLO-World stays on CPU for compatibility or as configured
        self.yolo_model.to("cpu")
        print("✅ YOLO-World chargé")

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
        Segments each ingredient using the Roboflow SAM API.
        Step 1: embed the image once
        Step 2: segment each ingredient using the center point of its YOLO bbox
        """
        import requests
        ROBOFLOW_BASE_URL = "https://serverless.roboflow.com"

        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        img = PILImage.open(image_path)
        total_area = img.width * img.height

        print("Step 3/4: Roboflow SAM API (Two-step)...")
        # ── Step 1: embed the image once (reused for all ingredients) ──
        try:
            def embed_call():
                resp = requests.post(
                    f"{ROBOFLOW_BASE_URL}/sam/embed_image",
                    params={"api_key": self.roboflow_api_key},
                    json={
                        "image": {"type": "base64", "value": image_b64},
                        "image_id": "meal_image"
                    },
                    timeout=30
                )
                resp.raise_for_status()
                return resp.json()
            
            call_with_retry(embed_call)
        except Exception as e:
            print(f"  ⚠️  Roboflow SAM Embedding failed: {e}")
            return [{**det, "masque": None, "surface_px": 0, "surface_pct": 0.0} for det in detections]

        results = []
        for det in detections:
            # Skip fallback detections
            if det.get("detecte_par") == "groq_vision_only" or det["bbox"] == [0, 0, 0, 0]:
                results.append({**det, "masque": None, "surface_px": 0, "surface_pct": 0.0})
                continue

            x1, y1, x2, y2 = det["bbox"]
            cx = (x1 + x2) / 2   # center x of YOLO bbox
            cy = (y1 + y2) / 2   # center y of YOLO bbox

            def segment_call():
                resp = requests.post(
                    f"{ROBOFLOW_BASE_URL}/sam/segment_image",
                    params={"api_key": self.roboflow_api_key},
                    json={
                        "image_id": "meal_image",
                        "point_coords": [[cx, cy]],
                        "point_labels": [1]      # 1 = positive point (include this object)
                    },
                    timeout=30
                )
                resp.raise_for_status()
                return resp.json()

            try:
                data = call_with_retry(segment_call)
                # Pick the highest-confidence mask
                masks = data.get("masks", [])
                if masks:
                    best = max(masks, key=lambda m: m.get("predicted_iou", 0))
                    # Calculate mask area from the polygon points
                    pts = best.get("segmentation", [[]])
                    if pts and len(pts[0]) > 2:
                        poly = np.array(pts[0]).reshape(-1, 2)
                        mask_area = int(cv2.contourArea(poly.astype(np.float32)))
                    else:
                        mask_area = 0
                else:
                    mask_area = 0
            except Exception as e:
                print(f"  ⚠️  Roboflow SAM failed for '{det['ingredient']}': {e}")
                mask_area = 0

            results.append({
                **det,
                "masque": None,
                "surface_px": mask_area,
                "surface_pct": round((mask_area / total_area) * 100, 2) if total_area else 0.0
            })

        return results

    def analyser_nutrition_groq(self, dish_name: str, ingredients_data: list, profil: dict) -> dict:
        prompt = f"""
You are an expert clinical nutritionist specialized in diabetes.
Analyze this meal for a patient with the following profile:
{json.dumps(profil, indent=2)}

Meal identified: {dish_name}
Ingredients detected (with visual surface coverage):
{json.dumps([{ 'ing': d['ingredient'], 'surf': d['surface_pct'] } for d in ingredients_data], indent=2)}

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
        
        # 3. Roboflow SAM
        print(f"Step 3/4: Roboflow SAM API...")
        detections_final = self.segmenter_ingredients_sam(image_path, detections)
        
        # 4. Nutrition Analysis
        print(f"Step 4/4: Nutrition Analysis...")
        nutrition_res = self.analyser_nutrition_groq(vision_res["dish"], detections_final, profil)
        
        # Clean results for serialisation
        clean_ingredients = []
        for d in detections_final:
            clean_ingredients.append({
                "ingredient": d["ingredient"],
                "confiance_visuelle": d["confiance"],
                "surface_pct": d["surface_pct"]
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
