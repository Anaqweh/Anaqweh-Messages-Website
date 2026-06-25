from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
template = root / "templates" / "registrations" / "spark_fill_form.html"

if not template.exists():
    print("ERROR: spark_fill_form.html غير موجود.")
    sys.exit(1)

html = template.read_text(encoding="utf-8", errors="ignore")

required = {
    "رفع صورة الهوية": ["loadImageFile", 'type="file"', "idPreview"],
    "الكاميرا": ["startCamera", "cameraPreview"],
    "قراءة الهوية OCR": ["Tesseract", "runOCR"],
    "الصورة المخفية للهوية": ["idImageData"],
    "تعبئة الاسم": ["full_name"],
    "تعبئة الجنسية": ["nationality"],
    "تعبئة تاريخ الميلاد": ["date_of_birth"],
    "تعبئة رقم الهوية": ["emirates_id"],
    "الجنس ذكر/أنثى": ['name="gender"', "Male", "Female"],
    "توقيع مقدم الطلب": ["signatureCanvas", "signatureData"],
}

errors = []

for label, markers in required.items():
    if not all(marker in html for marker in markers):
        errors.append(f"{label}: missing {markers}")

if errors:
    print("REGISTRATION GUARDRAIL FAILED")
    for err in errors:
        print("-", err)
    sys.exit(1)

print("REGISTRATION GUARDRAIL PASSED")
