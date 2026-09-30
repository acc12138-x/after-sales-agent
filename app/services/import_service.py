"""Excel 导入服务：客户批量导入。"""
from __future__ import annotations
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 临时文件目录
IMPORT_DIR = Path("./data/imports")
IMPORT_DIR.mkdir(parents=True, exist_ok=True)


# 标准字段
FIELD_DEFS = [
    {"key": "name",             "label": "客户姓名", "required": True,  "type": "str"},
    {"key": "phone",            "label": "手机号",   "required": True,  "type": "str", "unique": True},
    {"key": "email",            "label": "邮箱",     "required": False, "type": "str"},
    {"key": "address",          "label": "地址",     "required": False, "type": "str"},
    {"key": "vip_level",        "label": "VIP等级",  "required": False, "type": "str"},
    {"key": "total_orders",     "label": "订单数",   "required": False, "type": "int"},
    {"key": "total_refunds",    "label": "退款数",   "required": False, "type": "int"},
    {"key": "total_complaints", "label": "投诉数",   "required": False, "type": "int"},
]

FIELD_KEYS = {f["key"] for f in FIELD_DEFS}
FIELD_LABELS = {f["label"]: f["key"] for f in FIELD_DEFS}

# 中文别名 → 标准 key
ALIASES = {
    "姓名": "name", "客户名": "name", "name": "name",
    "手机": "phone", "电话": "phone", "手机号码": "phone",
    "phone": "phone", "tel": "phone",
    "email": "email", "电子邮箱": "email",
    "地址": "address", "详细地址": "address",
    "vip": "vip_level", "会员等级": "vip_level", "vip等级": "vip_level",
    "订单数量": "total_orders", "订单总数": "total_orders",
    "退款次数": "total_refunds", "退款总数": "total_refunds",
    "投诉次数": "total_complaints", "投诉总数": "total_complaints",
}


def save_upload(content_bytes: bytes, filename: str) -> Tuple[str, str]:
    """保存上传文件，返回 (token, saved_path)。"""
    token = uuid.uuid4().hex
    ext = os.path.splitext(filename)[1].lower() or ".xlsx"
    path = IMPORT_DIR / f"{token}{ext}"
    with open(path, "wb") as f:
        f.write(content_bytes)
    return token, str(path)


def get_upload_path(token: str) -> Optional[str]:
    """根据 token 找到临时文件路径。"""
    for ext in [".xlsx", ".xls", ".csv"]:
        p = IMPORT_DIR / f"{token}{ext}"
        if p.exists():
            return str(p)
    return None


def parse_file(path: str) -> Tuple[List[str], List[Dict]]:
    """解析 Excel/CSV，返回 (headers, rows)。"""
    ext = os.path.splitext(path)[1].lower()

    if ext == ".csv":
        import csv
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = list(reader.fieldnames or [])
            rows = list(reader)
        return headers, rows

    # xlsx / xls
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        rows_raw = list(ws.iter_rows(values_only=True))
        if not rows_raw:
            return [], []
        headers = [str(h).strip() if h is not None else "" for h in rows_raw[0]]
        rows = []
        for r in rows_raw[1:]:
            d = {}
            for i, h in enumerate(headers):
                d[h] = r[i] if i < len(r) else None
            rows.append(d)
        return headers, rows
    except Exception as e:
        raise ValueError(f"解析 Excel 失败：{e}")


def auto_mapping(headers: List[str]) -> Dict[str, str]:
    """自动识别 Excel 列 → 系统字段。"""
    mapping = {}
    for h in headers:
        h_clean = str(h).strip()
        if not h_clean:
            continue
        # 1. 直接匹配 label
        if h_clean in FIELD_LABELS:
            mapping[h_clean] = FIELD_LABELS[h_clean]
            continue
        # 2. 别名匹配（忽略大小写）
        h_low = h_clean.lower()
        for alias, key in ALIASES.items():
            if alias.lower() == h_low:
                mapping[h_clean] = key
                break
    return mapping


def preview(path: str, mapping: Optional[Dict[str, str]] = None) -> Dict:
    """返回预览数据。"""
    headers, rows = parse_file(path)
    auto_map = auto_mapping(headers)
    final_map = {**auto_map, **(mapping or {})}

    preview_rows = []
    for r in rows[:10]:
        row_dict = {}
        for h, key in final_map.items():
            if key:
                row_dict[key] = r.get(h)
        preview_rows.append(row_dict)

    return {
        "headers": headers,
        "auto_mapping": auto_map,
        "final_mapping": final_map,
        "field_defs": FIELD_DEFS,
        "total_rows": len(rows),
        "preview": preview_rows,
    }


def _coerce(value, typ: str):
    """类型转换。"""
    if value is None or value == "":
        return None
    if typ == "int":
        try:
            return int(float(value))
        except Exception:
            return None
    return str(value).strip()


def do_import(path: str, mapping: Dict[str, str]) -> Dict:
    """执行导入。"""
    from sqlalchemy import select
    from app.db.models.customer import Customer
    from app.db.session import session_scope

    headers, rows = parse_file(path)

    success = 0
    skipped = 0
    failed = 0
    errors = []

    # 已存在的手机号
    with session_scope() as s:
        existing_phones = set(
            r[0] for r in s.execute(select(Customer.phone)).all()
        )

    for i, r in enumerate(rows, 2):  # Excel 从第 2 行开始算数据
        try:
            row = {}
            for h, key in mapping.items():
                if key and key in FIELD_KEYS:
                    fdef = next((f for f in FIELD_DEFS if f["key"] == key), None)
                    row[key] = _coerce(r.get(h), fdef["type"] if fdef else "str")

            # 必填
            if not row.get("name"):
                failed += 1
                errors.append({"row": i, "reason": "客户姓名缺失"})
                continue
            if not row.get("phone"):
                failed += 1
                errors.append({"row": i, "reason": "手机号缺失"})
                continue

            phone = row["phone"]
            if phone in existing_phones:
                skipped += 1
                continue

            # 写库
            import uuid as _uuid
            cid = f"C{_uuid.uuid4().hex[:6].upper()}"
            with session_scope() as s:
                c = Customer(
                    customer_id=cid,
                    name=row["name"],
                    phone=phone,
                    email=row.get("email") or "",
                    address=row.get("address") or "",
                    vip_level=row.get("vip_level") or "normal",
                    total_orders=row.get("total_orders") or 0,
                    total_refunds=row.get("total_refunds") or 0,
                    total_complaints=row.get("total_complaints") or 0,
                )
                s.add(c)
            existing_phones.add(phone)
            success += 1
        except Exception as e:
            failed += 1
            errors.append({"row": i, "reason": str(e)[:100]})

    return {
        "total": len(rows),
        "success": success,
        "skipped": skipped,
        "failed": failed,
        "errors": errors[:20],
    }
