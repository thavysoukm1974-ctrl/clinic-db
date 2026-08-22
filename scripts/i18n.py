"""
i18n.py -- two-language UI text (English / Thai) with a saved preference.

How it works: the GUI is written in English. `t(text)` returns the Thai version
of that text when the language is set to Thai, or the English text itself when
it is English OR when no Thai translation is listed. So anything not translated
simply stays English -- nothing breaks. The chosen language is saved in a small
settings.json in the data folder, so it is remembered between runs.

IMPORTANT: the Thai strings below are a STARTING POINT written for review. A Thai
reader should check and correct them -- just edit the right-hand values in THAI.
Lao is intentionally not offered as a UI language (fonts/wording are unreliable),
but Lao text can still be typed into any field.
"""

import json

from init_db import DATA_DIR

_SETTINGS_FILE = DATA_DIR / "settings.json"

# The available UI languages, as {code: label-shown-in-the-menu}.
LANGUAGES = {"en": "English", "th": "ไทย"}

# English text  ->  Thai text. Keep the English EXACTLY as it appears in the UI.
# Anything missing here falls back to English automatically.
_THAI = {
    # window + navigation
    "Clinic system": "ระบบคลินิก",
    "View": "ดูข้อมูล",
    "Add / record": "เพิ่ม / บันทึก",
    "Patients": "ผู้ป่วย",
    "Reports": "รายงาน",
    "Selling": "การขาย",
    "Patients & visits": "ผู้ป่วยและการตรวจ",
    "Stock & catalog": "สต็อกและรายการยา",
    "Staff": "พนักงาน",
    "Stock": "สต็อก",
    "Alerts": "การแจ้งเตือน",
    "Follow-ups": "การติดตามผล",
    "Patient history": "ประวัติผู้ป่วย",
    "Money": "การเงิน",
    "Debts": "หนี้ค้างชำระ",
    "Record sale": "บันทึกการขาย",
    "Record visit": "บันทึกการตรวจ",
    "Add medicine": "เพิ่มยา",
    "Receive stock": "รับสต็อก",
    "Add patient": "เพิ่มผู้ป่วย",
    "Add employee": "เพิ่มพนักงาน",
    "Add supplier": "เพิ่มผู้จัดจำหน่าย",
    "Add follow-up": "เพิ่มการติดตามผล",
    # status bar
    "Back up now": "สำรองข้อมูลตอนนี้",
    "Check for updates": "ตรวจหาการอัปเดต",
    "Language:": "ภาษา:",
    # common buttons
    "Refresh": "รีเฟรช",
    "Add to sale": "เพิ่มลงรายการขาย",
    "Remove selected item": "ลบรายการที่เลือก",
    "Complete sale": "ทำการขายให้เสร็จ",
    "Clear": "ล้าง",
    "Show": "แสดง",
    "Show history": "แสดงประวัติ",
    "Save report...": "บันทึกรายงาน...",
    "Save visit": "บันทึกการตรวจ",
    "Receive": "รับเข้า",
    "Mark selected as paid": "ทำเครื่องหมายว่าชำระแล้ว",
    "Throw away selected batch": "ทิ้งล็อตที่เลือก",
    # common field labels
    "Medicine:": "ยา:",
    "Quantity:": "จำนวน:",
    "Sold by:": "ขายโดย:",
    "Paid now": "ชำระแล้ว",
    "Patient:": "ผู้ป่วย:",
    "Patient *:": "ผู้ป่วย *:",
    "Doctor:": "แพทย์:",
    "Sex:": "เพศ:",
    "Role:": "ตำแหน่ง:",
    "Supplier:": "ผู้จัดจำหน่าย:",
    "Name *:": "ชื่อ *:",
    "Phone:": "เบอร์โทร:",
    "Address:": "ที่อยู่:",
    "Note:": "หมายเหตุ:",
    "Form:": "รูปแบบ:",
    "Unit:": "หน่วย:",
    "Strength:": "ความแรง:",
    "Category:": "หมวดหมู่:",
    "Price:": "ราคา:",
    "Reorder at:": "สั่งซื้อเมื่อถึง:",
    "Diagnosis:": "การวินิจฉัย:",
    "Treatment:": "การรักษา:",
    "Qty given:": "จำนวนที่ให้:",
    "Give medicine:": "จ่ายยา:",
    "Daily dose:": "ขนาดต่อวัน:",
    "Quantity given:": "จำนวนที่ให้:",
    "Give medicine free (no charge)": "จ่ายยาฟรี (ไม่คิดเงิน)",
    "Paid now (untick = patient owes, pay later)": "ชำระแล้ว (ไม่ติ๊ก = ค้างชำระ จ่ายภายหลัง)",
    "Allow partial sale": "อนุญาตให้ขายบางส่วน",
    # panel headings
    "Current stock on hand": "สต็อกคงเหลือปัจจุบัน",
    "Expiring soon (within 30 days)": "ใกล้หมดอายุ (ภายใน 30 วัน)",
    "Low on stock": "สต็อกใกล้หมด",
    "Record a sale": "บันทึกการขาย",
    "Scheduled follow-ups": "การติดตามผลที่นัดไว้",
    "Money owed (pay later)": "เงินที่ค้างชำระ (จ่ายภายหลัง)",
    "Add a patient": "เพิ่มผู้ป่วย",
    "Add a staff member": "เพิ่มพนักงาน",
    "Add a supplier": "เพิ่มผู้จัดจำหน่าย",
    "Record a patient visit": "บันทึกการตรวจผู้ป่วย",
    "Add a medicine to the catalog": "เพิ่มยาเข้ารายการ",
    "Receive stock (add a batch)": "รับสต็อก (เพิ่มล็อต)",
    "Monthly report": "รายงานประจำเดือน",
    "Report": "รายงาน",
    "Items in this sale:": "รายการในการขายนี้:",
    "Add each medicine to the sale, then click Complete sale.":
        "เพิ่มยาแต่ละอย่างลงในการขาย แล้วกดทำการขายให้เสร็จ",
    # table column headers
    "Medicine": "ยา",
    "On hand": "คงเหลือ",
    "Unit": "หน่วย",
    "Qty": "จำนวน",
    "Expiry": "วันหมดอายุ",
    "Status": "สถานะ",
    "Reorder at": "สั่งซื้อเมื่อถึง",
    "Patient": "ผู้ป่วย",
    "Phone": "เบอร์โทร",
    "Amount owed": "ยอดค้างชำระ",
    "Sale date": "วันที่ขาย",
    "Date": "วันที่",
    "Diagnosis": "การวินิจฉัย",
    "Seen by": "ตรวจโดย",
    "Medicine given": "ยาที่จ่าย",
    "Runs out": "หมดเมื่อ",
    "Days ago": "กี่วันก่อน",
    # date + remaining field labels
    "Date of birth (YYYY-MM-DD):": "วันเกิด (ปปปป-ดด-วว):",
    "Date (YYYY-MM-DD):": "วันที่ (ปปปป-ดด-วว):",
    "Start date (YYYY-MM-DD):": "วันเริ่ม (ปปปป-ดด-วว):",
    "Expiry (YYYY-MM-DD):": "วันหมดอายุ (ปปปป-ดด-วว):",
    "Buy price / unit:": "ราคาซื้อ / หน่วย:",
    "   If pay later, patient:": "   ถ้าจ่ายภายหลัง ผู้ป่วย:",
    # report period controls + hints
    "Report": "รายงาน",
    "Month": "เดือน",
    "Day": "วัน",
    "Add a follow-up (check-in when medicine runs out)":
        "เพิ่มการติดตามผล (ติดตามเมื่อยาหมด)",
    "(Form = its shape; Unit = how you count and sell it)":
        "(รูปแบบ = ลักษณะยา; หน่วย = วิธีนับและขาย)",
    "Red = out of stock    Yellow = low, reorder soon":
        "แดง = หมดสต็อก    เหลือง = ใกล้หมด ควรสั่งซื้อ",
    "All open follow-ups. 'DUE' means the medicine should have run out -- call them.":
        "การติดตามผลที่เปิดอยู่ทั้งหมด 'DUE' หมายถึงยาน่าจะหมดแล้ว โทรหาผู้ป่วย",
    "Sales not yet paid. Select one and mark it paid when the patient settles up.":
        "การขายที่ยังไม่ชำระ เลือกหนึ่งรายการแล้วทำเครื่องหมายว่าชำระเมื่อผู้ป่วยจ่ายเงิน",
    # report text (labels only; numbers are added after them)
    "CLINIC MONTHLY REPORT": "รายงานคลินิกประจำเดือน",
    "CLINIC DAILY REPORT": "รายงานคลินิกประจำวัน",
    "Month:": "เดือน:",
    "Day:": "วัน:",
    "MONEY IN  (sales)": "เงินเข้า  (การขาย)",
    "Total sales:": "จำนวนการขาย:",
    "Revenue received:": "รายได้ที่รับแล้ว:",
    "Still owed (unpaid):": "ยังค้างชำระ:",
    "Total if all paid:": "รวมถ้าชำระครบ:",
    "By channel:": "แยกตามช่องทาง:",
    "from patient visits:": "จากการตรวจผู้ป่วย:",
    "from walk-in buyers:": "จากลูกค้าหน้าร้าน:",
    "Best sellers (by quantity):": "ขายดี (ตามจำนวน):",
    "SALES BY STAFF  (who sold)": "การขายตามพนักงาน  (ใครขาย)",
    "DEBTS  (unpaid sales this period)": "หนี้ค้างชำระ  (การขายที่ยังไม่จ่ายในช่วงนี้)",
    "Total owed:": "รวมค้างชำระ:",
    "MONEY OUT  (restocking)": "เงินออก  (เติมสต็อก)",
    "Total reorder spend:": "รวมค่าสั่งซื้อ:",
    "By supplier:": "แยกตามผู้จัดจำหน่าย:",
    "By medicine:": "แยกตามยา:",
    "PROFIT  (on what was sold)": "กำไร  (จากที่ขายไป)",
    "Revenue (all sales):": "รายได้ (การขายทั้งหมด):",
    "Cost of goods sold:": "ต้นทุนสินค้าที่ขาย:",
    "Gross profit:": "กำไรขั้นต้น:",
    "sold": "ขายแล้ว",
    "sales": "ครั้ง",
    "(none)": "(ไม่มี)",
    "(no sales)": "(ไม่มีการขาย)",
}

_lang = "en"


def load_language():
    """Read the saved language ('en' or 'th') at start-up. Defaults to English."""
    global _lang
    try:
        _lang = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8")).get("language", "en")
    except Exception:
        _lang = "en"
    if _lang not in LANGUAGES:
        _lang = "en"
    return _lang


def set_language(code):
    """Change and save the language. Takes effect when the app is reopened."""
    global _lang
    _lang = code if code in LANGUAGES else "en"
    try:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(json.dumps({"language": _lang}), encoding="utf-8")
    except Exception:
        pass


def current_language():
    return _lang


def t(text):
    """Return `text` in the current language (Thai if set and a translation
    exists, otherwise the English text unchanged)."""
    if _lang == "th":
        return _THAI.get(text, text)
    return text
