"""Thumbnail generation module using Nano Banana Pro (Gemini).

Generates YouTube thumbnails by sending base template images and prompts
to the Gemini image generation API (generateContent with IMAGE response).

Environment variables:
    GEMINI_API_KEY  - Google Gemini API key (required)
    GEMINI_MODEL    - Model name (default: gemini-3-pro-image-preview)

Template structure (templates/pattern{1,2,3}/):
    base.png    - Base template image
    prompt.txt  - Prompt template with {variables}
    config.json - Pattern configuration (variables, inputs)

Patterns:
    Pattern 1 (対談)  : 2-person circular frames, requires lecturer image
    Pattern 2 (グルコン): Smartphone 45% buried, requires phone screen image
    Pattern 3 (1on1)  : Text-only, no image replacement
"""

import base64
import json
import logging
import mimetypes
import os
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3-pro-image-preview"

# Mapping from record pattern field to template directory name
PATTERN_MAP = {
    "対談": "pattern1",
    "パターン1": "pattern1",
    "pattern1": "pattern1",
    "グルコン": "pattern2",
    "パターン2": "pattern2",
    "pattern2": "pattern2",
    "1on1": "pattern3",
    "パターン3": "pattern3",
    "pattern3": "pattern3",
}


def generate_thumbnail(record: dict, base_dir: str = ".") -> str:
    """Generate a thumbnail image from a Notion record.

    Determines the pattern from the record, loads the corresponding template,
    builds the prompt with variable substitution, optionally attaches images,
    calls the Gemini API, and saves the generated thumbnail.

    Args:
        record:   Parsed Notion record dict (from notion.py parse_master_record).
                  Expected keys vary by pattern but typically include:
                  - パターン (str): pattern identifier
                  - サムネ文言 (str): thumbnail text
                  - 講師名 (str): lecturer name
                  - ジャンル (str): genre (patterns 1 & 2)
                  - 生徒名 (str): student name (pattern 3)
                  - phone_screen_path (str): path to phone screenshot (pattern 2)
        base_dir: Project root directory path.

    Returns:
        Absolute path to the saved generated thumbnail image.

    Raises:
        ValueError: If pattern is missing or unrecognized.
        FileNotFoundError: If template files or required images are not found.
        RuntimeError: If the Gemini API call fails or returns no image.
    """
    base = Path(base_dir).resolve()

    # --- Determine pattern ---
    pattern_raw = (record.get("pattern") or record.get("パターン", "")).strip()
    pattern_dir_name = PATTERN_MAP.get(pattern_raw)
    if not pattern_dir_name:
        raise ValueError(
            f"Unrecognized pattern: '{pattern_raw}'. "
            f"Expected one of: {list(PATTERN_MAP.keys())}"
        )

    pattern_dir = base / "templates" / pattern_dir_name
    if not pattern_dir.is_dir():
        raise FileNotFoundError(f"Template directory not found: {pattern_dir}")

    logger.info("Using pattern: %s (%s)", pattern_raw, pattern_dir_name)

    # --- Load template ---
    base_image_bytes, prompt_template, config = _load_template(str(pattern_dir))
    logger.info("Loaded template: %s", config.get("name", pattern_dir_name))

    # --- Build prompt with variable substitution ---
    # Map Japanese config variable names to parsed record English keys
    _var_key_map = {
        "サムネ文言": "thumbnail_text",
        "講師名": "lecturer_name",
        "ジャンル": "genre",
        "生徒名": "student_name",
    }
    variables = config.get("variables", {})
    prompt = prompt_template
    for var_name in variables:
        placeholder = "{" + var_name + "}"
        record_key = _var_key_map.get(var_name, var_name)
        value = record.get(record_key) or record.get(var_name, "")
        if not value:
            logger.warning("Variable '%s' is empty in record", var_name)
        prompt = prompt.replace(placeholder, str(value))

    logger.debug("Final prompt:\n%s", prompt)

    # --- Prepare images ---
    images: list[tuple[str, bytes]] = []

    # Image 1 is always the base template
    images.append(("image/png", base_image_bytes))

    # Image 2 depends on pattern
    inputs = config.get("inputs", {})
    if "image2" in inputs:
        if pattern_dir_name == "pattern1":
            # Pattern 1: lecturer image for right circle
            lecturer_name = record.get("lecturer_name") or record.get("講師名", "")
            lecturer_image_path = _find_lecturer_image(lecturer_name, str(base))
            if not lecturer_image_path:
                raise FileNotFoundError(
                    f"No lecturer image found for: '{lecturer_name}'"
                )
            logger.info("Using lecturer image: %s", lecturer_image_path)
            mime = mimetypes.guess_type(lecturer_image_path)[0] or "image/png"
            images.append((mime, Path(lecturer_image_path).read_bytes()))

        elif pattern_dir_name == "pattern2":
            # Pattern 2: phone screen image
            phone_screen_path = record.get("phone_screen_path", "")
            if not phone_screen_path:
                raise ValueError(
                    "Pattern 2 requires 'phone_screen_path' in record"
                )
            phone_path = Path(phone_screen_path)
            if not phone_path.is_file():
                raise FileNotFoundError(
                    f"Phone screen image not found: {phone_screen_path}"
                )
            logger.info("Using phone screen image: %s", phone_screen_path)
            mime = mimetypes.guess_type(str(phone_path))[0] or "image/png"
            images.append((mime, phone_path.read_bytes()))

    # --- Call Gemini API (with retry) ---
    import time
    generated_bytes = None
    for attempt in range(1, 4):
        logger.info("Calling Gemini API for thumbnail generation (attempt %d/3)...", attempt)
        try:
            generated_bytes = _call_gemini_api(prompt, images)
            break
        except RuntimeError as e:
            if "did not contain image data" in str(e) and attempt < 3:
                logger.warning("Gemini returned no image, retrying in 3s...")
                time.sleep(3)
            else:
                raise
    if generated_bytes is None:
        raise RuntimeError("Gemini API failed to generate image after 3 attempts")

    # --- Save result ---
    output_dir = base / "assets" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_text = (record.get("thumbnail_text") or record.get("サムネ文言", "thumbnail"))[:20].replace("/", "_")
    output_filename = f"{pattern_dir_name}_{safe_text}_{timestamp}.png"
    output_path = output_dir / output_filename

    output_path.write_bytes(generated_bytes)
    logger.info("Thumbnail saved: %s", output_path)

    return str(output_path)


def _load_template(pattern_dir: str) -> tuple[bytes, str, dict]:
    """Load template files from a pattern directory.

    Args:
        pattern_dir: Path to the pattern directory containing
                     base.png, prompt.txt, and config.json.

    Returns:
        A tuple of (base_image_bytes, prompt_template_string, config_dict).

    Raises:
        FileNotFoundError: If any required template file is missing.
    """
    pattern_path = Path(pattern_dir)

    base_image_path = pattern_path / "base.png"
    prompt_path = pattern_path / "prompt.txt"
    config_path = pattern_path / "config.json"

    if not base_image_path.is_file():
        raise FileNotFoundError(f"Base image not found: {base_image_path}")
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    base_image_bytes = base_image_path.read_bytes()
    prompt_template = prompt_path.read_text(encoding="utf-8")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    logger.debug(
        "Loaded template from %s: base=%d bytes, prompt=%d chars",
        pattern_dir,
        len(base_image_bytes),
        len(prompt_template),
    )

    return base_image_bytes, prompt_template, config


def _find_lecturer_image(name: str, base_dir: str) -> str | None:
    """Find a lecturer image file matching the given name.

    Searches for files in assets/lecturer-images/ whose filename
    contains the lecturer name.

    Args:
        name: Lecturer name to search for (e.g., "陸", "はなこ").
        base_dir: Project root directory path.

    Returns:
        Absolute path to the matching image file, or None if not found.
        If multiple files match, returns the first one sorted by filename.
    """
    if not name:
        logger.warning("Empty lecturer name provided")
        return None

    images_dir = Path(base_dir) / "assets" / "lecturer-images"
    if not images_dir.is_dir():
        logger.warning("Lecturer images directory not found: %s", images_dir)
        return None

    matches = sorted(
        p for p in images_dir.iterdir()
        if p.is_file() and name in p.name
    )

    if not matches:
        logger.warning("No image found for lecturer: '%s'", name)
        return None

    selected = matches[0]
    logger.info(
        "Found %d image(s) for '%s', using: %s",
        len(matches),
        name,
        selected.name,
    )
    return str(selected)


def _call_gemini_api(prompt: str, images: list[tuple[str, bytes]]) -> bytes:
    """Call the Gemini API to generate a thumbnail image.

    Sends a multimodal request with text prompt and image parts to the
    Gemini generateContent endpoint, requesting both IMAGE and TEXT
    response modalities.

    Args:
        prompt: The text prompt describing the desired edits.
        images: List of (mime_type, image_bytes) tuples to include
                as inline image parts in the request.

    Returns:
        The generated image as raw bytes (PNG).

    Raises:
        EnvironmentError: If GEMINI_API_KEY is not set.
        RuntimeError: If the API returns an error or no image data.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("Missing required environment variable: GEMINI_API_KEY")

    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    url = f"{GEMINI_API_BASE}/{model}:generateContent"

    # Build request parts: images first, then text prompt
    parts: list[dict] = []
    for mime_type, image_bytes in images:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": encoded,
            }
        })
    parts.append({"text": prompt})

    payload = {
        "contents": [
            {
                "parts": parts,
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
        },
    }

    logger.info("Sending request to Gemini API: model=%s, images=%d", model, len(images))

    response = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=120,
    )

    if response.status_code != 200:
        error_detail = response.text[:500]
        logger.error(
            "Gemini API error (HTTP %d): %s", response.status_code, error_detail
        )
        raise RuntimeError(
            f"Gemini API request failed with status {response.status_code}: "
            f"{error_detail}"
        )

    result = response.json()

    # Parse response to find generated image
    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini API returned no candidates")

    content_parts = candidates[0].get("content", {}).get("parts", [])

    for part in content_parts:
        inline_data = part.get("inline_data") or part.get("inlineData")
        if inline_data:
            img_data = inline_data.get("data")
            mime = inline_data.get("mime_type") or inline_data.get("mimeType", "unknown")
            if img_data and mime.startswith("image/"):
                image_bytes = base64.b64decode(img_data)
                logger.info(
                    "Received generated image: %d bytes, mime=%s",
                    len(image_bytes),
                    mime,
                )
                return image_bytes

    # Log any text response for debugging
    for part in content_parts:
        if "text" in part:
            logger.debug("Gemini text response: %s", part["text"][:200])

    raise RuntimeError(
        "Gemini API response did not contain image data. "
        f"Response parts: {[list(p.keys()) for p in content_parts]}"
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Example usage with a mock record
    sample_record = {
        "パターン": "1on1",
        "講師名": "みくぽん",
        "サムネ文言": "アフィ案件 今後の計画",
        "生徒名": "えむさん",
    }

    project_root = str(Path(__file__).resolve().parent.parent)
    logger.info("Project root: %s", project_root)

    try:
        result_path = generate_thumbnail(sample_record, base_dir=project_root)
        print(f"\nGenerated thumbnail: {result_path}")
    except EnvironmentError as e:
        print(f"\nEnvironment error: {e}")
        print("Set GEMINI_API_KEY to run this example.")
    except Exception as e:
        print(f"\nError: {e}")
