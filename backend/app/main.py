from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

app = FastAPI(title="EDI Translator/Validator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RuleResult(BaseModel):
    code: str
    severity: str  # ERROR/WARN
    message: str
    segment_index: Optional[int] = None

class ParsedEDI(BaseModel):
    interchange: Dict[str, Any]
    functional_group: Dict[str, Any]
    transaction: Dict[str, Any]
    segments: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]

def infer_delimiters(raw: str):
    segment_term = "~"
    element_sep = "*"
    component_sep = ":"

    if raw.startswith("ISA"):
        try:
            element_sep = raw[3]
            first_line = raw.split("\n")[0]
            parts = first_line.split(element_sep)
            if len(parts) >= 17 and parts[16]:
                component_sep = parts[16][0]
            for c in ["~", "\r\n", "\n", "\r"]:
                if c in raw:
                    segment_term = c
                    break
        except Exception:
            pass
    return segment_term, element_sep, component_sep

def split_segments(raw: str, seg_term: str) -> List[str]:
    return [s.strip() for s in raw.split(seg_term) if s.strip()]

def parse_elements(segment: str, element_sep: str) -> List[str]:
    return segment.split(element_sep)

def detect_transaction(segments: List[str], element_sep: str) -> Optional[str]:
    for seg in segments:
        if seg.startswith("ST" + element_sep):
            elems = parse_elements(seg, element_sep)
            return elems[1] if len(elems) > 1 else None
    return None

def validate_generic(segments: List[str], element_sep: str) -> List[Dict[str, Any]]:
    errors: List[Dict[str, Any]] = []
    if not segments or not segments[0].startswith("ISA" + element_sep):
        errors.append(RuleResult(code="GEN001", severity="ERROR", message="Missing or invalid ISA as first segment").dict())
    if not any(s.startswith("GS" + element_sep) for s in segments):
        errors.append(RuleResult(code="GEN002", severity="ERROR", message="Missing GS segment").dict())
    if not any(s.startswith("GE" + element_sep) for s in segments):
        errors.append(RuleResult(code="GEN003", severity="ERROR", message="Missing GE segment").dict())
    if not any(s.startswith("IEA" + element_sep) for s in segments):
        errors.append(RuleResult(code="GEN004", severity="ERROR", message="Missing IEA segment").dict())
    st_count = sum(1 for s in segments if s.startswith("ST" + element_sep))
    se_count = sum(1 for s in segments if s.startswith("SE" + element_sep))
    if st_count != se_count:
        errors.append(RuleResult(code="GEN005", severity="ERROR", message=f"ST/SE count mismatch ({st_count}/{se_count})").dict())
    return errors

def validate_850(segments: List[str], element_sep: str) -> List[Dict[str, Any]]:
    errors: List[Dict[str, Any]] = []
    required = {"ST": False, "BEG": False}
    for i, seg in enumerate(segments):
        tag = seg.split(element_sep)[0]
        if tag in required:
            required[tag] = True
        if seg.startswith("BEG" + element_sep):
            elems = parse_elements(seg, element_sep)
            if len(elems) < 6 or not elems[3]:
                errors.append(RuleResult(code="850_BEG_PO", severity="ERROR", message="BEG missing Purchase Order number", segment_index=i).dict())
    for tag, ok in required.items():
        if not ok:
            errors.append(RuleResult(code=f"850_REQ_{tag}", severity="ERROR", message=f"Missing required {tag} segment").dict())
    # Ordering rule: BEG before any PO1
    beg_idx = next((i for i,s in enumerate(segments) if s.startswith("BEG"+element_sep)), -1)
    first_po1 = next((i for i,s in enumerate(segments) if s.startswith("PO1"+element_sep)), -1)
    if first_po1 != -1 and (beg_idx == -1 or first_po1 < beg_idx):
        errors.append(RuleResult(code="850_ORDER_BEFORE_BEG", severity="ERROR", message="PO1 appears before BEG").dict())
    return errors

def validate_810(segments: List[str], element_sep: str) -> List[Dict[str, Any]]:
    errors: List[Dict[str, Any]] = []
    required = {"ST": False, "BIG": False}
    for i, seg in enumerate(segments):
        tag = seg.split(element_sep)[0]
        if tag in required:
            required[tag] = True
        if seg.startswith("BIG" + element_sep):
            elems = parse_elements(seg, element_sep)
            if len(elems) < 5 or not elems[2] or not elems[4-1]:
                errors.append(RuleResult(code="810_BIG", severity="ERROR", message="BIG missing invoice/PO numbers", segment_index=i).dict())
    for tag, ok in required.items():
        if not ok:
            errors.append(RuleResult(code=f"810_REQ_{tag}", severity="ERROR", message=f"Missing required {tag} segment").dict())
    return errors

VALIDATORS = {"850": validate_850, "810": validate_810}

def parse_x12(raw: str) -> ParsedEDI:
    seg_term, elem_sep, comp_sep = infer_delimiters(raw)
    segs = split_segments(raw, seg_term)

    seg_objs = []
    for s in segs:
        parts = parse_elements(s, elem_sep)
        if not parts or not parts[0]:
            continue
        seg_objs.append({"tag": parts[0], "elements": parts[1:], "raw": s})

    txn = detect_transaction(segs, elem_sep)

    errors: List[Dict[str, Any]] = []
    errors.extend(validate_generic(segs, elem_sep))
    if txn in VALIDATORS:
        errors.extend(VALIDATORS[txn](segs, elem_sep))

    isa = next((o for o in seg_objs if o["tag"] == "ISA"), None)
    gs = next((o for o in seg_objs if o["tag"] == "GS"), None)
    st = next((o for o in seg_objs if o["tag"] == "ST"), None)

    return ParsedEDI(
        interchange={"ISA": isa},
        functional_group={"GS": gs},
        transaction={"ST": st, "set_id": txn},
        segments=seg_objs,
        errors=errors,
    )

@app.post("/parse", response_model=ParsedEDI)
async def parse_endpoint(file: UploadFile = File(...)):
    raw = (await file.read()).decode("utf-8", errors="ignore")
    result = parse_x12(raw)
    return result

@app.get("/health")
def health():
    return {"status": "ok"}
