from __future__ import annotations

from html import escape
from io import BytesIO
import os
import textwrap
from urllib.parse import unquote, urlparse
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.utils import timezone
import httpx
from pypdf import PdfReader
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import KidsAssistantTurn, KidsDailyCheckin, KidsInstructionDocument, KidsProfile, KidsStorySession
from .serializers import (
    KidsAssistantMessageSerializer,
    KidsCheckinSerializer,
    KidsDailyCheckinSerializer,
    KidsProfileSerializer,
    KidsStoryRequestSerializer,
    KidsStorySessionSerializer,
)
from .services import (
    extract_instruction_lines,
    extract_instruction_checklist,
    format_instruction_checklist,
    rebuild_instruction_index,
    retrieve_relevant_chunks,
    summarize_rules_for_prompt,
)


def _compute_lie_risk_from_libreface_output(lib_output) -> float:
    # Heuristic: favor neutral/happy as lower risk; negative emotions raise risk.
    # libreface may return a list of per-frame dicts or a single dict.
    def frame_to_scores(frame: dict) -> tuple[float, float]:
        # returns (positive_score, negative_score)
        pos_keys = ("happy", "smile", "neutral")
        neg_keys = ("sad", "anger", "fear", "disgust", "contempt")
        pos = 0.0
        neg = 0.0
        for k, v in frame.items():
            key = str(k).lower()
            try:
                val = float(v)
            except Exception:
                continue
            if any(pk in key for pk in pos_keys):
                pos += val
            if any(nk in key for nk in neg_keys):
                neg += val
            # handle Action Units (au12 is smile)
            if key.startswith("au"):
                # treat AU12 (lip corner puller) as positive
                if "au12" in key:
                    pos += val * 0.8
                else:
                    # other AUs increase expressiveness -> small negative weight
                    neg += val * 0.15
        return pos, neg

    frames = []
    if lib_output is None:
        return 0.1
    if isinstance(lib_output, dict):
        frames = [lib_output]
    elif isinstance(lib_output, (list, tuple)):
        frames = list(lib_output)
    else:
        try:
            # pandas DataFrame-like
            frames = lib_output.to_dict(orient="records")
        except Exception:
            return 0.1

    if not frames:
        return 0.1

    total_indicator = 0.0
    for frame in frames:
        pos, neg = frame_to_scores(frame)
        denom = pos + neg + 1e-6
        # indicator in [0,1]: higher when negative dominates
        indicator = max(0.0, (neg - pos) / denom)
        total_indicator += indicator
    avg_indicator = total_indicator / len(frames)
    # map to lie risk with a small baseline
    lie_risk = 0.1 + avg_indicator * 0.8
    if lie_risk > 1.0:
        lie_risk = 1.0
    if lie_risk < 0.0:
        lie_risk = 0.0
    return round(float(lie_risk), 3)
from .voice_cloning import (
    VoiceCloneConfigurationError,
    VoiceCloneProviderError,
    synthesize_with_parent_voice,
)


def _resolve_patient_id(request) -> int:
    if getattr(request.user, "role", None) == "patient":
        return int(request.user.id)
    raw = request.query_params.get("patient_id") or request.data.get("patient_id")
    if not raw:
        raise ValueError("patient_id is required for non-patient users")
    return int(raw)


def _media_url(request, path: str) -> str:
    return request.build_absolute_uri(f"{settings.MEDIA_URL}{path}")


def _save_upload(request, upload, folder: str, allowed_prefixes: tuple[str, ...]) -> str:
    content_type = (getattr(upload, "content_type", "") or "").lower()
    if allowed_prefixes and not any(content_type.startswith(prefix) for prefix in allowed_prefixes):
        raise ValueError(f"Unsupported file type: {content_type or 'unknown'}")
    extension = os.path.splitext(upload.name or "")[1] or ""
    path = default_storage.save(f"kids/{folder}/{uuid4().hex}{extension}", upload)
    return _media_url(request, path)


def _huggingface_token() -> str:
    return (
        os.getenv("HUGGINGFACE_API_KEY", "")
        or os.getenv("HF_TOKEN", "")
        or os.getenv("HUGGINGFACEHUB_API_TOKEN", "")
    ).strip()


def _local_media_path_from_url(image_url: str) -> str:
    parsed_path = unquote(urlparse(image_url or "").path)
    media_url = settings.MEDIA_URL
    if not parsed_path.startswith(media_url):
        return ""
    relative_path = parsed_path.removeprefix(media_url).lstrip("/")
    media_root = settings.MEDIA_ROOT.resolve()
    candidate = (media_root / relative_path).resolve()
    if not str(candidate).startswith(str(media_root)) or not candidate.exists():
        return ""
    return str(candidate)


def _generate_huggingface_image_with_status(request, prompt: str, model: str, folder: str) -> tuple[str, str]:
    token = _huggingface_token()
    if not token:
        return "", "Missing HUGGINGFACE_API_KEY/HF_TOKEN."
    sdk_error = ""
    try:
        from huggingface_hub import InferenceClient

        image = InferenceClient(api_key=token, provider="auto").text_to_image(prompt=prompt, model=model)
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        path = default_storage.save(f"kids/{folder}/{uuid4().hex}.png", ContentFile(image_bytes.getvalue()))
        return _media_url(request, path), ""
    except Exception as exc:
        sdk_error = str(exc)[:300]
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"https://api-inference.huggingface.co/models/{model}",
            headers={"Authorization": f"Bearer {token}"},
            json={"inputs": prompt},
        )
    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        detail = response.text[:300].strip()
        error = f"Hugging Face SDK failed: {sdk_error}. " if sdk_error else ""
        return "", f"{error}Hugging Face returned {response.status_code}: {detail}"
    if content_type.startswith("image/"):
        suffix = ".png" if "png" in content_type else ".jpg"
        path = default_storage.save(f"kids/{folder}/{uuid4().hex}{suffix}", ContentFile(response.content))
        return _media_url(request, path), ""
    try:
        data = response.json()
    except ValueError:
        return "", f"Hugging Face returned non-image content: {content_type or 'unknown content type'}."
    if isinstance(data, dict):
        image_url = data.get("image_url", "") or ""
        if image_url:
            return image_url, ""
        return "", f"Hugging Face returned JSON without image_url: {str(data)[:300]}"
    return "", f"Hugging Face returned unsupported payload: {str(data)[:300]}"


def _generate_huggingface_image_to_image_with_status(
    request,
    prompt: str,
    reference_image_url: str,
    model: str,
    folder: str,
) -> tuple[str, str]:
    token = _huggingface_token()
    if not token:
        return "", "Missing HUGGINGFACE_API_KEY/HF_TOKEN."
    reference_path = _local_media_path_from_url(reference_image_url)
    if not reference_path:
        return "", "Child reference photo is not available in local media storage."
    try:
        from huggingface_hub import InferenceClient

        image = InferenceClient(api_key=token, provider="auto").image_to_image(
            image=reference_path,
            prompt=prompt,
            negative_prompt=(
                "photo, photorealistic, realistic skin texture, pasted photo, poster, card, frame, title, caption, "
                "speech bubble, text, letters, words, logo, watermark, scary, medical distress, distorted face, distorted hands, cropped head, blurry"
            ),
            model=model,
        )
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        path = default_storage.save(f"kids/{folder}/{uuid4().hex}.png", ContentFile(image_bytes.getvalue()))
        return _media_url(request, path), ""
    except Exception as exc:
        return "", str(exc)[:300]


def _generate_huggingface_image(request, prompt: str, model: str, folder: str) -> str:
    image_url, _error = _generate_huggingface_image_with_status(request, prompt, model, folder)
    return image_url


def _kids_image_model(env_name: str, default: str = "black-forest-labs/FLUX.1-schnell") -> str:
    deprecated_models = {"jbilcke-hf/ai-comic-factory"}
    configured = os.getenv(env_name, "").strip()
    if configured and "/" in configured and configured not in deprecated_models:
        return configured
    avatar_model = os.getenv("KIDS_AVATAR_MODEL", "").strip()
    if avatar_model and "/" in avatar_model and avatar_model not in deprecated_models:
        return avatar_model
    return default


def _kids_image_to_image_model(default: str = "Qwen/Qwen-Image-Edit") -> str:
    configured = os.getenv("KIDS_STORY_IMAGE_TO_IMAGE_MODEL", "").strip()
    if configured and "/" in configured:
        return configured
    return default


def _wrap_svg_text(text: str, width: int = 44, max_lines: int = 4) -> list[str]:
    cleaned = " ".join((text or "").split())
    lines = textwrap.wrap(cleaned, width=width)
    return lines[:max_lines] or ["A bright healthy choice adventure begins."]


def _save_story_fallback_image(request, title: str, mood: str, narrative: str) -> str:
    is_reward = mood == "reward"
    sky = "#d9f7ff" if is_reward else "#e8ecff"
    accent = "#22c55e" if is_reward else "#8b5cf6"
    ground = "#b7f0c1" if is_reward else "#c7d2fe"
    lines = _wrap_svg_text(narrative)
    text_nodes = "\n".join(
        f'<text x="80" y="{430 + index * 34}" font-size="24" fill="#164e63">{escape(line)}</text>'
        for index, line in enumerate(lines)
    )
    badge_text = "Great choices" if is_reward else "Try again tomorrow"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="768" viewBox="0 0 1024 768">
  <rect width="1024" height="768" fill="{sky}"/>
  <circle cx="830" cy="128" r="72" fill="#fff7ad"/>
  <path d="M0 580 C180 520 300 640 470 580 C650 520 790 560 1024 510 L1024 768 L0 768 Z" fill="{ground}"/>
  <path d="M266 226 C356 142 520 132 620 232 C708 320 704 458 602 536 C494 620 326 584 250 462 C198 378 206 282 266 226 Z" fill="#ffffff" opacity="0.86"/>
  <path d="M382 270 L488 194 L598 270 L554 270 L554 386 L420 386 L420 270 Z" fill="{accent}"/>
  <circle cx="456" cy="326" r="14" fill="#ffffff"/>
  <circle cx="520" cy="326" r="14" fill="#ffffff"/>
  <path d="M452 360 C478 384 508 384 536 360" fill="none" stroke="#ffffff" stroke-width="12" stroke-linecap="round"/>
  <path d="M642 246 L774 178 L744 322 Z" fill="#f97316"/>
  <path d="M672 254 L726 228 L716 286 Z" fill="#ffffff" opacity="0.9"/>
  <circle cx="174" cy="176" r="10" fill="#38bdf8"/>
  <circle cx="222" cy="120" r="7" fill="#f97316"/>
  <circle cx="722" cy="118" r="8" fill="#22c55e"/>
  <rect x="66" y="398" width="720" height="172" rx="24" fill="#ffffff" opacity="0.88"/>
  <text x="80" y="376" font-family="Arial, sans-serif" font-size="42" font-weight="700" fill="#0f172a">{escape(title)}</text>
  {text_nodes}
  <rect x="776" y="578" width="196" height="54" rx="27" fill="{accent}"/>
  <text x="874" y="613" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#ffffff">{badge_text}</text>
</svg>"""
    path = default_storage.save(f"kids/story-scenes/{uuid4().hex}.svg", ContentFile(svg.encode("utf-8")))
    return _media_url(request, path)


def _save_local_cartoon_story_image(request, reference_path: str, title: str, mood: str, narrative: str) -> str:
    try:
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
    except Exception:
        return ""

    try:
        source = Image.open(reference_path).convert("RGB")
    except Exception:
        return ""

    canvas_size = 1024
    is_reward = mood == "reward"
    bg_top = (218, 247, 255) if is_reward else (232, 236, 255)
    bg_bottom = (183, 240, 193) if is_reward else (199, 210, 254)
    accent = (34, 197, 94) if is_reward else (139, 92, 246)

    background = Image.new("RGB", (canvas_size, canvas_size), bg_top)
    draw = ImageDraw.Draw(background)
    for y in range(canvas_size):
        ratio = y / canvas_size
        color = tuple(int(bg_top[i] * (1 - ratio) + bg_bottom[i] * ratio) for i in range(3))
        draw.line([(0, y), (canvas_size, y)], fill=color)

    draw.ellipse((740, 88, 900, 248), fill=(255, 247, 173))
    draw.polygon([(0, 760), (260, 690), (520, 760), (760, 700), (1024, 748), (1024, 1024), (0, 1024)], fill=bg_bottom)

    portrait = ImageOps.exif_transpose(source)
    portrait.thumbnail((600, 680))
    crop = ImageOps.pad(portrait, (560, 680), method=Image.Resampling.LANCZOS, color=(255, 255, 255), centering=(0.5, 0.35))
    smooth = crop.filter(ImageFilter.MedianFilter(size=3)).filter(ImageFilter.SMOOTH_MORE)
    color = ImageEnhance.Color(smooth).enhance(1.45)
    contrast = ImageEnhance.Contrast(color).enhance(1.16)
    cartoon = ImageOps.posterize(contrast, 4)
    edges = ImageOps.invert(crop.convert("L").filter(ImageFilter.FIND_EDGES)).point(lambda p: 255 if p > 210 else 45)
    edges = ImageOps.colorize(edges, black=(39, 39, 42), white=(255, 255, 255))
    cartoon = Image.blend(cartoon, edges, 0.18)

    mask = Image.new("L", cartoon.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, cartoon.width, cartoon.height), radius=34, fill=255)
    background.paste(cartoon, (232, 118), mask)

    panel_y = 762
    draw.rounded_rectangle((64, panel_y, 960, 966), radius=28, fill=(255, 255, 255))
    draw.rounded_rectangle((64, panel_y, 960, 966), radius=28, outline=accent, width=4)

    try:
        title_font = ImageFont.truetype("arial.ttf", 42)
        body_font = ImageFont.truetype("arial.ttf", 24)
        badge_font = ImageFont.truetype("arialbd.ttf", 22)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        badge_font = ImageFont.load_default()

    draw.text((92, panel_y + 28), title[:42], fill=(15, 23, 42), font=title_font)
    for index, line in enumerate(_wrap_svg_text(narrative, width=62, max_lines=3)):
        draw.text((92, panel_y + 88 + index * 32), line, fill=(22, 78, 99), font=body_font)

    badge_text = "Great choices" if is_reward else "Try again tomorrow"
    draw.rounded_rectangle((704, 82, 964, 138), radius=28, fill=accent)
    draw.text((834, 100), badge_text, anchor="mm", fill=(255, 255, 255), font=badge_font)

    image_bytes = BytesIO()
    background.save(image_bytes, format="PNG")
    path = default_storage.save(f"kids/story-scenes/{uuid4().hex}.png", ContentFile(image_bytes.getvalue()))
    return _media_url(request, path)


def _story_visual_prompt(mood: str, child_direction: str = "") -> str:
    if mood == "reward":
        scene = (
            "bright cheerful space playground adventure, the child hero chooses water and a healthy snack, "
            "friendly space helper nearby, colorful planets, warm celebration feeling"
        )
    else:
        scene = (
            "gentle try-again space adventure, the child hero sets aside a sugary drink and chooses water, "
            "friendly space helper nearby, calm supportive feeling, hopeful colors"
        )
    if child_direction:
        scene = f"{scene}. Extra visual direction: {child_direction[:220]}"
    return (
        "Fully redraw the reference child as a polished 2D cartoon storybook hero. "
        "Clean hand-drawn children's book illustration, cel shading, soft outlines, expressive friendly face, full scene composition. "
        "Preserve the child's hairstyle, skin tone, age, and general outfit colors from the reference photo, but make it clearly illustrated, not photographic. "
        f"Scene: {scene}. "
        "No text, no title, no captions, no speech bubbles, no labels, no poster border, no UI card, no watermark. "
        "Do not place the original photo inside the image; redraw the child as cartoon art."
    )


def _kids_llm_model() -> str:
    configured = os.getenv("KIDS_MAIN_ASSISTANT_MODEL", "").strip()
    if configured and "/" not in configured:
        return configured
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"


def _call_groq_chat(messages: list[dict[str, str]], max_tokens: int = 220) -> tuple[str, str]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = _kids_llm_model()
    if not api_key:
        return "", model
    with httpx.Client(timeout=45.0) as client:
        response = client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.55,
                "max_tokens": max_tokens,
            },
        )
    if response.status_code >= 400 and model != "llama-3.3-70b-versatile":
        model = "llama-3.3-70b-versatile"
        with httpx.Client(timeout=45.0) as client:
            response = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.55,
                    "max_tokens": max_tokens,
                },
            )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip(), model


def _fallback_assistant_reply(profile: KidsProfile, rules: list[str], child_message: str) -> str:
    name = profile.assistant_name or "Buddy"
    avoid = [rule.split(":", 1)[1].strip() for rule in rules if rule.lower().startswith("avoid:")]
    do_items = [rule.split(":", 1)[1].strip() for rule in rules if rule.lower().startswith("do:")]
    if avoid or do_items:
        avoid_text = ", ".join(avoid) if avoid else "the foods and drinks the doctor said to skip"
        do_text = ", ".join(do_items) if do_items else "your healthy habits"
        return (
            f"Hi, I am {name}. Let's check today carefully. Did you have any of these: {avoid_text}? "
            f"And did you do these: {do_text}? You can answer one by one."
        )
    rule = rules[0] if rules else "follow your doctor's plan"
    return f"Hi, I am {name}. Did you follow this doctor rule today: {rule}? Tell me what happened."


def _checklist_items(checklist: dict[str, list[str]]) -> list[str]:
    items: list[str] = []
    for section in ("avoid", "do", "alert"):
        for item in checklist.get(section, []):
            items.append(f"{section}:{item}")
    return items


def _is_yes_answer(text: str) -> bool:
    normalized = f" {text.lower()} "
    return any(
        phrase in normalized
        for phrase in (
            " yes ",
            " yeah ",
            " yep ",
            " i did ",
            " done ",
            " checked ",
            " took ",
            " drank water ",
            " ate healthy ",
            " all done ",
        )
    )


def _is_no_answer(text: str) -> bool:
    normalized = f" {text.lower()} "
    return any(
        phrase in normalized
        for phrase in (
            " no ",
            " nope ",
            " none ",
            " nothing ",
            " didn't ",
            " did not ",
            " no candy ",
            " no soda ",
            " no juice ",
            " not yet ",
        )
    )


def _items_mentioned_in_text(
    text: str,
    checklist: dict[str, list[str]],
    section_filter: set[str] | None = None,
) -> list[tuple[str, str]]:
    lowered = (text or "").lower()
    mentioned: list[tuple[str, str]] = []
    for section, items in checklist.items():
        if section_filter and section not in section_filter:
            continue
        for item in items:
            item_lower = item.lower().strip()
            words = [
                word
                for word in item_lower.replace("with", " ").replace("and", " ").replace(",", " ").split()
                if len(word) > 3
            ]
            if item_lower in lowered or any(word in lowered for word in words):
                mentioned.append((section, item))
    return mentioned


def _latest_question_text(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if "?" not in cleaned:
        return cleaned
    before_question = cleaned.rsplit("?", 1)[0]
    start = max(before_question.rfind("."), before_question.rfind("!"), before_question.rfind("?"))
    return f"{before_question[start + 1:].strip()}?"


def _infer_answered_items(
    child_message: str,
    checklist: dict[str, list[str]],
    previous_assistant_reply: str = "",
) -> dict[str, str]:
    text = (child_message or "").lower()
    answered: dict[str, str] = {}
    if not text:
        return answered
    yes_answer = _is_yes_answer(text)
    no_answer = _is_no_answer(text)
    latest_question = _latest_question_text(previous_assistant_reply)
    previous_lower = latest_question.lower()
    section_filter: set[str] | None = None
    if "eat or drink any of these" in previous_lower or "avoid" in previous_lower:
        section_filter = {"avoid"}
    elif (
        "did you do this today" in previous_lower
        or "did ye do this today" in previous_lower
        or "did you drink" in previous_lower
        or "did ye drink" in previous_lower
        or "balanced meals" in previous_lower
        or "blood sugar" in previous_lower
        or "insulin" in previous_lower
    ):
        section_filter = {"do"}
    elif "did you feel" in previous_lower or "did ye feel" in previous_lower:
        section_filter = {"alert"}
    asked_items = _items_mentioned_in_text(latest_question, checklist, section_filter)
    if asked_items and (yes_answer or no_answer):
        for section, item in asked_items:
            key = f"{section}:{item}"
            if section == "avoid":
                answered[key] = "had_avoid_item" if yes_answer and not no_answer else "avoided"
            else:
                answered[key] = "done" if yes_answer and not no_answer else "not_done"
        return answered
    negative_all = no_answer
    positive_all = yes_answer
    for section, items in checklist.items():
        for item in items:
            key = f"{section}:{item}"
            words = [word for word in item.lower().replace("with", " ").replace("and", " ").split() if len(word) > 3]
            matched = any(word in text for word in words)
            if section == "avoid":
                if matched and not negative_all:
                    answered[key] = "had_avoid_item"
                elif matched or negative_all:
                    answered[key] = "avoided"
            elif matched:
                answered[key] = "done" if not no_answer else "not_done"
            elif positive_all and len(items) == 1:
                answered[key] = "done"
    return answered


def _merge_checklist_state(current: dict[str, str], inferred: dict[str, str]) -> dict[str, str]:
    merged = dict(current)
    for key, value in inferred.items():
        previous = merged.get(key)
        if previous == "had_avoid_item" and value == "avoided":
            continue
        if previous == "not_done" and value == "done":
            continue
        merged[key] = value
    return merged


def _assess_checklist_state(checklist: dict[str, list[str]], checklist_state: dict[str, str]) -> dict[str, object]:
    all_items = _checklist_items(checklist)
    if not all_items:
        return {
            "complete": False,
            "followed": False,
            "lie_risk_score": 0.1,
            "feedback": "Upload the doctor instructions first so Buddy can choose the story path from the real rules.",
            "story_direction": "incomplete: upload doctor instructions before choosing the story path.",
            "had_avoid_items": [],
            "missed_do_items": [],
            "alert_items": [],
            "missing_items": [],
        }
    missing_items = [item for item in all_items if item not in checklist_state]
    had_avoid_items = [item for item, value in checklist_state.items() if item.startswith("avoid:") and value == "had_avoid_item"]
    missed_do_items = [item for item, value in checklist_state.items() if item.startswith("do:") and value == "not_done"]
    alert_items = [item for item, value in checklist_state.items() if item.startswith("alert:") and value in {"done", "had_avoid_item"}]
    followed = not had_avoid_items and not missed_do_items and not alert_items and not missing_items
    if had_avoid_items:
        feedback = "Thanks for being honest. Since an avoid food or drink happened today, the story will use the try-again path."
        story_direction = "warning: the hero learns from eating or drinking an avoid item and chooses a better plan next time."
    elif missed_do_items:
        feedback = "Thanks for being honest. Since one healthy habit was missed today, the story will use the try-again path."
        story_direction = "warning: the hero learns from a missed healthy habit and makes a better plan."
    elif alert_items:
        feedback = "Thanks for telling me. Since a body-alert feeling happened today, tell a parent and the story will stay careful."
        story_direction = "warning: the hero tells a trusted grown-up about a body-alert feeling."
    elif missing_items:
        feedback = "Keep going with Buddy's questions so the story path can be chosen from today's answers."
        story_direction = "incomplete: ask Buddy the remaining check-in questions before choosing the story path."
    else:
        feedback = "Great job following the doctor's plan today. You unlocked a happy story path."
        story_direction = "reward: the hero followed the doctor rules and gets a bright celebration adventure."
    return {
        "complete": not missing_items or bool(had_avoid_items or missed_do_items or alert_items),
        "followed": followed,
        "lie_risk_score": 0.1,
        "feedback": feedback,
        "story_direction": story_direction,
        "had_avoid_items": had_avoid_items,
        "missed_do_items": missed_do_items,
        "alert_items": alert_items,
        "missing_items": missing_items,
    }


def _next_missing_question(checklist: dict[str, list[str]], missing_items: list[str]) -> str:
    if not missing_items:
        return ""
    avoid_items = [item.split(":", 1)[1] for item in missing_items if item.startswith("avoid:")]
    do_items = [item.split(":", 1)[1] for item in missing_items if item.startswith("do:")]
    alert_items = [item.split(":", 1)[1] for item in missing_items if item.startswith("alert:")]
    if avoid_items:
        return f"Did you eat or drink any of these today: {', '.join(avoid_items[:4])}? You can answer yes or no."
    if do_items:
        item = do_items[0]
        return f"Did you do this today: {item}? You can answer yes or no."
    if alert_items:
        return f"Did you feel any of these today: {', '.join(alert_items[:3])}? You can answer yes or no."
    return ""


class KidsProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_id = _resolve_patient_id(request)
        profile, _ = KidsProfile.objects.get_or_create(patient_id=patient_id)
        return Response(KidsProfileSerializer(profile).data)

    def post(self, request):
        patient_id = _resolve_patient_id(request)
        profile, _ = KidsProfile.objects.get_or_create(patient_id=patient_id)
        serializer = KidsProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class KidsDoctorInstructionUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        patient_id = _resolve_patient_id(request)
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Missing PDF file in form-data key 'file'."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.content_type not in {"application/pdf", "application/x-pdf"}:
            return Response({"detail": "Only PDF files are supported."}, status=status.HTTP_400_BAD_REQUEST)

        pdf_bytes = upload.read()
        reader = PdfReader(BytesIO(pdf_bytes))
        document_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        rules = extract_instruction_lines(document_text)

        KidsInstructionDocument.objects.filter(patient_id=patient_id).update(is_active=False)
        doc = KidsInstructionDocument.objects.create(
            patient_id=patient_id,
            source_filename=upload.name,
            document_text=document_text,
            extracted_rules=rules,
            is_active=True,
        )
        rebuild_instruction_index(doc)

        return Response(
            {
                "document_id": doc.id,
                "source_filename": doc.source_filename,
                "rules_count": len(rules),
                "rules": rules[:12],
            },
            status=status.HTTP_201_CREATED,
        )


class KidsAvatarGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        patient_id = _resolve_patient_id(request)
        profile, _ = KidsProfile.objects.get_or_create(patient_id=patient_id)
        prompt = (request.data.get("prompt") or profile.avatar_prompt or profile.persona_prompt or "").strip()
        if len(prompt) < 5:
            return Response({"detail": "Add an avatar generation prompt first."}, status=status.HTTP_400_BAD_REQUEST)

        profile.avatar_prompt = prompt
        model = _kids_image_model("KIDS_AVATAR_MODEL")
        full_prompt = (
            "Friendly child-safe 2D cartoon assistant avatar, centered circular portrait, bright clean background. "
            f"{prompt}"
        )

        try:
            image_url = _generate_huggingface_image(request, full_prompt, model, "avatars")
            if image_url:
                profile.avatar_image_url = image_url
        except Exception:
            # Keep the saved prompt even if the provider is down or the free endpoint is sleeping.
            pass

        profile.save(update_fields=["avatar_prompt", "avatar_image_url", "updated_at"])
        return Response(
            {
                "profile": KidsProfileSerializer(profile).data,
                "provider": "huggingface",
                "model": model,
                "prompt": full_prompt,
                "image_url": profile.avatar_image_url,
                "status": "generated" if profile.avatar_image_url else "prompt_saved",
            }
        )


class KidsParentVoiceUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        patient_id = _resolve_patient_id(request)
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Missing audio file in form-data key 'file'."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            voice_url = _save_upload(request, upload, "voices", ("audio/", "video/webm"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        profile, _ = KidsProfile.objects.get_or_create(patient_id=patient_id)
        profile.parent_voice_sample_url = voice_url
        profile.parent_voice_profile_id = f"local-parent-voice-{patient_id}"
        profile.save(update_fields=["parent_voice_sample_url", "parent_voice_profile_id", "updated_at"])
        return Response(KidsProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class KidsParentVoiceSynthesizeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        patient_id = _resolve_patient_id(request)
        text = str(request.data.get("text", "")).strip()
        if not text:
            return Response({"detail": "text is required."}, status=status.HTTP_400_BAD_REQUEST)
        profile, _ = KidsProfile.objects.get_or_create(patient_id=patient_id)
        try:
            audio_bytes, content_type, voice_id = synthesize_with_parent_voice(profile, text)
        except VoiceCloneConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_424_FAILED_DEPENDENCY)
        except VoiceCloneProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response = HttpResponse(audio_bytes, content_type=content_type)
        if voice_id.startswith("pocket:"):
            provider = "pocket"
        elif voice_id.startswith("fish:"):
            provider = "fish"
        else:
            provider = "elevenlabs"
        response["X-Voice-Clone-Provider"] = provider
        response["X-Voice-Id"] = voice_id
        return response


class KidsChildPhotoUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        patient_id = _resolve_patient_id(request)
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Missing image file in form-data key 'file'."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            photo_url = _save_upload(request, upload, "child-photos", ("image/",))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        profile, _ = KidsProfile.objects.get_or_create(patient_id=patient_id)
        photos = profile.child_reference_photos if isinstance(profile.child_reference_photos, list) else []
        profile.child_reference_photos = [*photos, photo_url]
        profile.save(update_fields=["child_reference_photos", "updated_at"])
        return Response(KidsProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class KidsLieDetectorView(APIView):
    """Accept an uploaded image or short video and run LibreFace to extract facial attributes
    and return a heuristic lie risk score.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        patient_id = _resolve_patient_id(request)
        upload = request.FILES.get("file") or request.FILES.get("video")
        if upload is None:
            return Response({"detail": "Missing image/video file in form-data key 'file' or 'video'."}, status=status.HTTP_400_BAD_REQUEST)

        content_type = (getattr(upload, "content_type", "") or "").lower()
        extension = os.path.splitext(upload.name or "")[1].lower()
        octet_allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm", ".mov"}
        try:
            if content_type == "application/octet-stream" and extension in octet_allowed_extensions:
                path = default_storage.save(f"kids/lie-detections/{uuid4().hex}{extension}", upload)
                media_url = _media_url(request, path)
            else:
                media_url = _save_upload(request, upload, "lie-detections", ("image/", "video/", "video/mp4", "video/webm"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        local_path = _local_media_path_from_url(media_url)
        if not local_path:
            return Response({"detail": "Cannot access saved file from server storage."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            import libreface
        except Exception as exc:
            return Response(
                {
                    "detail": (
                        "libreface import failed. Ensure runtime dependencies are installed "
                        f"in the active backend env. Import error: {str(exc)[:240]}"
                    )
                },
                status=status.HTTP_424_FAILED_DEPENDENCY,
            )

        try:
            # call libreface; try CPU by default
            attributes = libreface.get_facial_attributes(local_path, device=os.getenv("LIBREFACE_DEVICE", "cpu"))
        except Exception as exc:
            message = str(exc)[:400]
            if "No face landmarks" in message:
                return Response(
                    {"detail": "No face detected in the uploaded image/video. Try a clearer front-facing face."},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            return Response({"detail": f"LibreFace inference failed: {str(exc)[:400]}"}, status=status.HTTP_502_BAD_GATEWAY)

        try:
            lie_risk = _compute_lie_risk_from_libreface_output(attributes)
        except Exception:
            lie_risk = 0.1

        # persist a small checkin record with lie risk (optional)
        try:
            KidsDailyCheckin.objects.create(
                patient_id=patient_id,
                child_message=f"lie-detection: {os.path.basename(local_path)}",
                followed_instructions=False,
                lie_risk_score=float(lie_risk),
                assistant_feedback="lie-detection snapshot",
            )
        except Exception:
            # non-fatal if DB write fails
            pass

        attributes_payload = attributes
        if hasattr(attributes, "to_dict"):
            try:
                attributes_payload = attributes.to_dict(orient="records")
            except Exception:
                try:
                    attributes_payload = attributes.to_dict()
                except Exception:
                    attributes_payload = {"detail": "libreface output could not be serialized"}

        first_item = attributes_payload[0] if isinstance(attributes_payload, list) and attributes_payload else attributes_payload
        if not isinstance(first_item, dict):
            first_item = {}
        attributes_summary = {
            "facial_expression": first_item.get("facial_expression"),
            "detected_aus": first_item.get("detected_aus"),
            "au_intensities": first_item.get("au_intensities"),
            "pitch": first_item.get("pitch"),
            "yaw": first_item.get("yaw"),
            "roll": first_item.get("roll"),
        }

        include_raw = request.query_params.get("include_raw") == "1"

        return Response({
            "media_url": media_url,
            "local_path": local_path,
            "attributes": attributes_payload if include_raw else None,
            "attributes_summary": attributes_summary,
            "lie_risk_score": lie_risk,
        })


class KidsRagContextView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_id = _resolve_patient_id(request)
        query = request.query_params.get("query", "").strip()
        chunks = retrieve_relevant_chunks(patient_id=patient_id, query=query, limit=4)
        active_doc = KidsInstructionDocument.objects.filter(patient_id=patient_id, is_active=True).first()
        rules = active_doc.extracted_rules if active_doc else []
        return Response(
            {
                "query": query,
                "rules_summary": summarize_rules_for_prompt(rules),
                "chunks": [chunk.chunk_text for chunk in chunks],
            }
        )


class KidsAssistantMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        patient_id = _resolve_patient_id(request)
        serializer = KidsAssistantMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        child_message = serializer.validated_data.get("message", "").strip()

        profile, _ = KidsProfile.objects.get_or_create(patient_id=patient_id)
        active_doc = KidsInstructionDocument.objects.filter(patient_id=patient_id, is_active=True).first()
        rules = active_doc.extracted_rules if active_doc else []
        checklist = extract_instruction_checklist(active_doc.document_text if active_doc else "")
        checklist_text = format_instruction_checklist(checklist)
        today = timezone.localdate()
        recent_turns = list(
            KidsAssistantTurn.objects.filter(patient_id=patient_id, created_at__date=today).order_by("-created_at")[:8]
        )
        recent_turns.reverse()
        checklist_state: dict[str, str] = {}
        for turn in recent_turns:
            if isinstance(turn.checklist_state, dict):
                checklist_state.update(turn.checklist_state)
        previous_assistant_reply = recent_turns[-1].assistant_reply if recent_turns else ""
        inferred_answers = _infer_answered_items(child_message, checklist, previous_assistant_reply)
        checklist_state = _merge_checklist_state(checklist_state, inferred_answers)
        all_items = _checklist_items(checklist)
        missing_items = [item for item in all_items if item not in checklist_state]
        assessment = _assess_checklist_state(checklist, checklist_state)
        if assessment["complete"]:
            missing_items = []
        next_question = _next_missing_question(checklist, missing_items)
        memory_text = "\n".join(
            f"Child: {turn.child_message}\nAssistant: {turn.assistant_reply}" for turn in recent_turns[-6:]
        )
        chunks = retrieve_relevant_chunks(patient_id=patient_id, query=child_message or "daily check-in", limit=4)
        rag_context = "\n".join(chunk.chunk_text for chunk in chunks) or summarize_rules_for_prompt(rules)
        persona = profile.persona_prompt.strip() or "friendly, patient, playful, and calm"
        assistant_name = profile.assistant_name or "Buddy"

        system_prompt = (
            "You are a warm child-safe diabetes care assistant inside a healthcare app. "
            "Speak naturally like a kind parent or older sibling, not like a form. Use the child's chosen persona lightly; do not let it hide the medical checklist. "
            "Use ONLY the doctor instructions and retrieved PDF context below for medical rules. "
            "Your job is not to quiz the child about what the doctor said. Your job is to check what the child actually did today. "
            "If the child has not answered the checklist yet, ask concrete yes/no questions using the exact items: first ask whether they ate or drank any AVOID items, then ask whether they completed each DO habit. "
            "For this diabetes PDF, good questions look like: 'Did you eat candy, drink soda or juice, or have desserts with added sugar?' and 'Did you drink water, eat a balanced meal, check blood sugar before breakfast and bedtime, and take insulin exactly as prescribed?' "
            "Ask only ONE focused question at a time unless grouping AVOID foods/drinks together. "
            "When the child says yes or no, interpret it in relation to your immediately previous question and the checklist state. "
            "If the memory says the child already answered some items, acknowledge them and ask only the missing items. "
            "If all items are answered, summarize whether today looks okay or not based only on the answers, and tell them you will use that for the story reward. "
            "Do not restart the check-in from the first question. Do not ask about items already answered. "
            "Do not diagnose, shame, scare, or invent rules. Keep it short, friendly, and easy for a child."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Assistant name: {assistant_name}\n"
                    f"Persona requested by child: {persona}\n"
                    f"Structured checklist from doctor PDF:\n{checklist_text or 'No structured checklist found.'}\n\n"
                    f"Conversation memory from today:\n{memory_text or 'No previous assistant turns today.'}\n\n"
                    f"Checklist items already answered:\n{checklist_state or 'None yet.'}\n\n"
                    f"Checklist items still missing:\n{missing_items or 'None.'}\n\n"
                    f"Current safety assessment:\n{assessment}\n\n"
                    f"Best next checklist question if anything is missing:\n{next_question or 'No more checklist questions.'}\n\n"
                    f"Doctor rules summary:\n{summarize_rules_for_prompt(rules)}\n\n"
                    f"Retrieved PDF context:\n{rag_context}\n\n"
                    f"Child said: {child_message or 'The child has just opened the assistant.'}\n\n"
                    "Reply directly to the child. If there is a best next checklist question, ask it naturally. "
                    "If no checklist question remains, give a short warm summary. If the assessment says followed=false, say the try-again story path is ready. If followed=true, say the reward story can be generated."
                ),
            },
        ]

        provider = "fallback"
        model = _kids_llm_model()
        try:
            reply, model = _call_groq_chat(messages)
            provider = "groq"
            if next_question and not _items_mentioned_in_text(reply, checklist):
                reply = f"Thanks for telling me. {next_question}"
        except Exception:
            if next_question:
                reply = f"Thanks for telling me. {next_question}"
            elif all_items:
                reply = str(assessment["feedback"])
            else:
                reply = _fallback_assistant_reply(profile, rules, child_message)
        if assessment["complete"] and not next_question:
            path_text = "reward story" if assessment["followed"] else "try-again story"
            reply = f"{assessment['feedback']} The {path_text} is ready to generate now."

        turn = KidsAssistantTurn.objects.create(
            patient_id=patient_id,
            child_message=child_message,
            assistant_reply=reply,
            checklist_state=checklist_state,
            provider=provider,
            model=model,
        )
        checkin = None
        if assessment["complete"]:
            checkin = KidsDailyCheckin.objects.filter(patient_id=patient_id, created_at__date=today).first()
            checkin_payload = {
                "child_message": "\n".join(
                    part
                    for part in (
                        memory_text,
                        f"Child: {child_message}" if child_message else "",
                        f"Assistant: {reply}",
                    )
                    if part
                )[-2500:],
                "followed_instructions": bool(assessment["followed"]),
                "lie_risk_score": float(assessment["lie_risk_score"]),
                "assistant_feedback": str(assessment["feedback"]),
            }
            if checkin:
                for field, value in checkin_payload.items():
                    setattr(checkin, field, value)
                checkin.save(update_fields=[*checkin_payload.keys()])
            else:
                checkin = KidsDailyCheckin.objects.create(patient_id=patient_id, **checkin_payload)

        return Response(
            {
                "reply": reply,
                "provider": provider,
                "model": model,
                "rules_used": rules[:8],
                "checklist": checklist,
                "checklist_state": checklist_state,
                "missing_items": missing_items,
                "next_question": next_question,
                "assessment": assessment,
                "checkin": KidsDailyCheckinSerializer(checkin).data if checkin else None,
                "turn_id": turn.id,
                "rag_context": rag_context,
            }
        )


class KidsAssistantHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        patient_id = _resolve_patient_id(request)
        deleted_count, _ = KidsAssistantTurn.objects.filter(patient_id=patient_id).delete()
        return Response({"deleted_count": deleted_count})


class KidsDailyCheckinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        patient_id = _resolve_patient_id(request)
        serializer = KidsCheckinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        active_doc = KidsInstructionDocument.objects.filter(patient_id=patient_id, is_active=True).first()
        rules = active_doc.extracted_rules if active_doc else []
        rules_summary = summarize_rules_for_prompt(rules)

        followed = payload["followed_instructions"]
        lie_risk_score = float(payload.get("lie_risk_score", 0.0))
        if followed and lie_risk_score <= 0.35:
            feedback = "Great job following the doctor's plan today. You unlocked a happy story path."
        elif followed:
            feedback = "Good effort. Let's keep being honest and consistent so the story remains bright."
        else:
            feedback = "Let's try again tomorrow. The story will include consequences until the doctor rules are respected."

        checkin = KidsDailyCheckin.objects.create(
            patient_id=patient_id,
            child_message=payload.get("child_message", ""),
            followed_instructions=followed,
            lie_risk_score=lie_risk_score,
            assistant_feedback=feedback,
        )
        return Response(
            {
                "checkin": KidsDailyCheckinSerializer(checkin).data,
                "rag_rules_summary": rules_summary,
            },
            status=status.HTTP_201_CREATED,
        )


class KidsStoryGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        patient_id = _resolve_patient_id(request)
        serializer = KidsStoryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        checkin = None
        checkin_id = payload.get("checkin_id")
        if checkin_id is not None:
            checkin = KidsDailyCheckin.objects.filter(id=checkin_id, patient_id=patient_id).first()
        if checkin is None:
            checkin = KidsDailyCheckin.objects.filter(patient_id=patient_id).first()

        profile, _ = KidsProfile.objects.get_or_create(patient_id=patient_id)
        active_doc = KidsInstructionDocument.objects.filter(patient_id=patient_id, is_active=True).first()
        rules = active_doc.extracted_rules if active_doc else []
        hero_name = profile.assistant_name or "Buddy"
        child_faces = profile.child_reference_photos
        followed = bool(checkin and checkin.followed_instructions and checkin.lie_risk_score <= 0.35)
        mood = "reward" if followed else "warning"
        title = "The Bright Path Adventure" if followed else "The Turning Clouds Mission"
        narrative = (
            f"{hero_name} and their young friend explored a colorful 2D world. "
            f"The doctor rules guided every choice: {', '.join(rules[:3]) if rules else 'be healthy and honest'}."
        )
        if followed:
            narrative += " Because the child followed instructions honestly, the world became brighter and everyone celebrated."
        else:
            narrative += " Because instructions were not followed, the world darkened and the hero had to solve a harder challenge."
        story_provider = "template"
        story_model = _kids_llm_model()
        story_messages = [
            {
                "role": "system",
                "content": (
                    "You write short, child-safe 2D cartoon story scenes for children with diabetes. "
                    "Use the doctor's rules as the moral of the scene. No fear, no shame, no medical advice beyond the rules. "
                    "Return only the story text, 120-180 words."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Assistant name: {hero_name}\n"
                    f"Avatar/persona: {profile.avatar_prompt or profile.persona_prompt}\n"
                    f"Doctor rules:\n{summarize_rules_for_prompt(rules)}\n"
                    f"Child followed rules: {followed}\n"
                    f"Child story direction: {payload.get('prompt') or 'surprise me'}"
                ),
            },
        ]
        try:
            llm_narrative, story_model = _call_groq_chat(story_messages, max_tokens=360)
            if llm_narrative:
                narrative = llm_narrative
                story_provider = "groq"
        except Exception:
            pass
        visual_direction = payload.get("prompt") or ""
        scene_image_prompt = _story_visual_prompt(mood, visual_direction)
        scene_image_url = ""
        story_image_model = _kids_image_model("KIDS_STORY_IMAGE_MODEL")
        story_image_to_image_model = _kids_image_to_image_model()
        image_reference_url = child_faces[-1] if isinstance(child_faces, list) and child_faces else ""
        image_generation_mode = "none"
        story_image_error = ""
        image_errors: list[str] = []
        if image_reference_url:
            hero_reference_prompt = scene_image_prompt
            try:
                generated_scene_url, image_to_image_error = _generate_huggingface_image_to_image_with_status(
                    request,
                    hero_reference_prompt,
                    image_reference_url,
                    story_image_to_image_model,
                    "story-scenes",
                )
                if generated_scene_url:
                    scene_image_url = generated_scene_url
                    scene_image_prompt = hero_reference_prompt
                    image_generation_mode = "child_photo_to_cartoon"
                elif image_to_image_error:
                    image_errors.append(f"Image-to-image failed: {image_to_image_error}")
            except Exception as exc:
                image_errors.append(f"Image-to-image failed: {str(exc)[:300]}")
        try:
            if not scene_image_url:
                generated_scene_url, text_to_image_error = _generate_huggingface_image_with_status(
                    request,
                    scene_image_prompt,
                    story_image_model,
                    "story-scenes",
                )
                if generated_scene_url:
                    scene_image_url = generated_scene_url
                    image_generation_mode = "text_to_image"
                elif text_to_image_error:
                    image_errors.append(f"Text-to-image failed: {text_to_image_error}")
        except Exception as exc:
            image_errors.append(f"Text-to-image failed: {str(exc)[:300]}")
        if not scene_image_url:
            image_generation_mode = "not_generated"
        story_image_error = " ".join(image_errors)[:900]

        story = KidsStorySession.objects.create(
            patient_id=patient_id,
            checkin=checkin,
            mood=mood,
            title=title,
            narrative=narrative,
            scene_image_prompt=scene_image_prompt,
            scene_image_url=scene_image_url,
            protagonist_face_refs=child_faces if isinstance(child_faces, list) else [],
            metadata={
                "llm_story_provider": story_provider,
                "llm_story_model": story_model,
                "image_model": story_image_model,
                "image_to_image_model": story_image_to_image_model,
                "image_reference_url": image_reference_url,
                "image_generation_mode": image_generation_mode,
                "image_status": (
                    "generated"
                    if not story_image_error
                    else "generated_with_fallback"
                    if image_generation_mode in {"child_photo_to_cartoon", "text_to_image"}
                    else "not_generated"
                ),
                "image_error": story_image_error,
                "voice_clone_provider": "local parent voice sample",
                "ai_service_url": getattr(settings, "AI_SERVICE_URL", ""),
            },
        )
        return Response(KidsStorySessionSerializer(story).data, status=status.HTTP_201_CREATED)


class KidsStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_id = _resolve_patient_id(request)
        profile, _ = KidsProfile.objects.get_or_create(patient_id=patient_id)
        active_doc = KidsInstructionDocument.objects.filter(patient_id=patient_id, is_active=True).first()
        latest_checkin = KidsDailyCheckin.objects.filter(patient_id=patient_id).first()
        latest_story = KidsStorySession.objects.filter(patient_id=patient_id).first()
        recent_turns = list(KidsAssistantTurn.objects.filter(patient_id=patient_id).order_by("-created_at")[:10])
        recent_turns.reverse()
        latest_turn = recent_turns[-1] if recent_turns else None
        latest_checklist = extract_instruction_checklist(active_doc.document_text if active_doc else "")
        latest_assessment = (
            _assess_checklist_state(latest_checklist, latest_turn.checklist_state)
            if latest_turn and isinstance(latest_turn.checklist_state, dict)
            else None
        )
        return Response(
            {
                "profile": KidsProfileSerializer(profile).data,
                "active_instruction_doc": {
                    "id": active_doc.id,
                    "source_filename": active_doc.source_filename,
                    "rules": active_doc.extracted_rules,
                }
                if active_doc
                else None,
                "latest_checkin": KidsDailyCheckinSerializer(latest_checkin).data if latest_checkin else None,
                "latest_story": KidsStorySessionSerializer(latest_story).data if latest_story else None,
                "latest_assistant_assessment": latest_assessment,
                "recent_assistant_turns": [
                    {
                        "id": turn.id,
                        "child_message": turn.child_message,
                        "assistant_reply": turn.assistant_reply,
                        "checklist_state": turn.checklist_state,
                        "provider": turn.provider,
                        "model": turn.model,
                        "created_at": turn.created_at,
                    }
                    for turn in recent_turns
                ],
            }
        )
