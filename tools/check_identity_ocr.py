from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CANDIDATES = [
    PROJECT_ROOT / "templates" / "registrations" / "spark_fill_form.html",
    PROJECT_ROOT / "templates" / "registrations" / "fill_form.html",
]

required_any = {
    "camera": ["cameraPreview", "startCamera"],
    "capture_or_upload": ["capturePhoto", "loadImageFile", 'type="file"', "type='file'"],
    "ocr_engine": ["Tesseract", "recognize", "runOCR", "OCR"],
    "identity_preview": ["idPreview", "idImageData"],
}

optional_but_expected = {
    "emirates_id": ["emirates_id", "784"],
    "date_of_birth": ["date_of_birth"],
    "nationality": ["nationality"],
    "full_name": ["full_name"],
}

found_file = None
content = ""

for candidate in CANDIDATES:
    if candidate.exists():
        text = candidate.read_text(encoding="utf-8", errors="ignore")
        if any(marker in text for markers in required_any.values() for marker in markers):
            found_file = candidate
            content = text
            break

if not found_file:
    print("ERROR: لم يتم العثور على قالب يحتوي خاصية قراءة الهوية.")
    sys.exit(1)

errors = []

for group, markers in required_any.items():
    if not any(marker in content for marker in markers):
        errors.append(f"Missing required OCR marker group: {group} -> {markers}")

warnings = []

for group, markers in optional_but_expected.items():
    if not any(marker in content for marker in markers):
        warnings.append(f"Warning: expected field marker not found: {group} -> {markers}")

print(f"Identity OCR template checked: {found_file}")

if warnings:
    for warning in warnings:
        print(warning)

if errors:
    print("IDENTITY OCR CHECK FAILED")
    for error in errors:
        print(error)
    sys.exit(1)

print("IDENTITY OCR CHECK PASSED")
