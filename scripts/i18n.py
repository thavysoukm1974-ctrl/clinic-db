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

# Default language for a brand-new install (no settings.json yet). Thai, because
# the app is for a Thai/Lao-speaking clinic. Once the user picks a language it is
# saved and remembered.
_DEFAULT = "th"
_lang = _DEFAULT


def load_language():
    """Read the saved language ('en' or 'th') at start-up. A fresh install with
    no saved choice yet uses the default (Thai)."""
    global _lang
    try:
        _lang = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8")).get("language", _DEFAULT)
    except Exception:
        _lang = _DEFAULT
    if _lang not in LANGUAGES:
        _lang = _DEFAULT
    return _lang


def set_language(code):
    """Change and save the language. Takes effect when the app is reopened."""
    global _lang
    _lang = code if code in LANGUAGES else _DEFAULT
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


# The longer "?" help pop-ups, kept here in both languages. help_text(key)
# returns (title, body) for the current language. (Thai is a draft to review.)
HELP = {
    "report": {
        "en_title": "About this report",
        "th_title": "เกี่ยวกับรายงานนี้",
        "en": (
            "MONEY IN counts what was sold, split between sales made during "
            "patient visits and walk-in counter sales.\n\n"
            "MONEY OUT (reorder spend) is cash paid to BUY stock received in "
            "this period.\n\n"
            "COST OF GOODS SOLD is different: it is what the stock actually "
            "SOLD in this period had cost. You might buy a big batch one month "
            "and sell it over many months, so the two numbers differ on "
            "purpose.\n\n"
            "GROSS PROFIT = revenue minus cost of goods sold."),
        "th": (
            "เงินเข้า นับสิ่งที่ขายได้ แยกเป็นการขายระหว่างการตรวจผู้ป่วย "
            "และการขายหน้าร้าน\n\n"
            "เงินออก (ค่าสั่งซื้อ) คือเงินสดที่จ่ายเพื่อซื้อสต็อกที่รับเข้ามาในช่วงนี้\n\n"
            "ต้นทุนสินค้าที่ขาย ต่างกัน คือต้นทุนของสต็อกที่ขายไปจริงในช่วงนี้ "
            "คุณอาจซื้อยาล็อตใหญ่ในเดือนหนึ่งแล้วขายไปหลายเดือน "
            "ตัวเลขสองอย่างจึงต่างกันโดยตั้งใจ\n\n"
            "กำไรขั้นต้น = รายได้ ลบ ต้นทุนสินค้าที่ขาย"),
    },
    "form_unit": {
        "en_title": "Form vs Unit",
        "th_title": "รูปแบบ เทียบกับ หน่วย",
        "en": (
            "FORM is the medicine's physical shape: tablet, capsule, syrup, "
            "cream...\n\n"
            "UNIT is how you count and sell it: by the tablet, by the bottle, "
            "by the box...\n\n"
            "For pills they are usually the same word. For liquids they "
            "differ: a cough syrup's form is 'syrup' but you sell it by the "
            "'bottle'."),
        "th": (
            "รูปแบบ คือลักษณะทางกายภาพของยา: เม็ด แคปซูล น้ำเชื่อม ครีม...\n\n"
            "หน่วย คือวิธีที่คุณนับและขาย: เป็นเม็ด เป็นขวด เป็นกล่อง...\n\n"
            "ยาเม็ดมักเป็นคำเดียวกัน แต่ยาน้ำจะต่างกัน เช่น ยาน้ำเชื่อมแก้ไอ "
            "มีรูปแบบเป็น 'น้ำเชื่อม' แต่ขายเป็น 'ขวด'"),
    },
    "partial": {
        "en_title": "Allow partial sale",
        "th_title": "อนุญาตให้ขายบางส่วน",
        "en": (
            "If a customer asks for more than is in stock:\n\n"
            "TICKED -- sell them the amount that IS in stock (a partial "
            "amount), and the seller is told how much was short.\n\n"
            "UNTICKED -- sell none of this medicine in that case. Use this "
            "for medicine that should only be sold in full amounts, such as "
            "a complete course."),
        "th": (
            "ถ้าลูกค้าขอมากกว่าที่มีในสต็อก:\n\n"
            "ติ๊ก -- ขายเท่าที่มีในสต็อก (บางส่วน) และระบบจะบอกผู้ขายว่าขาดไปเท่าไร\n\n"
            "ไม่ติ๊ก -- ไม่ขายยานี้เลยในกรณีนั้น ใช้กับยาที่ควรขายเต็มจำนวนเท่านั้น "
            "เช่น ยาที่ต้องกินให้ครบคอร์ส"),
    },
    "runout": {
        "en_title": "How the run-out date is estimated",
        "th_title": "วิธีประมาณวันที่ยาหมด",
        "en": (
            "The expected run-out date is calculated from what you enter:\n\n"
            "    days of supply = quantity given / daily dose\n"
            "    run-out date = start date + days of supply\n\n"
            "Example: 10 tablets at 2 per day = 5 days.\n\n"
            "It is an estimate that assumes the medicine is taken as "
            "directed. The follow-up list shows patients whose estimated "
            "run-out date has passed, so they can be called to check in."),
        "th": (
            "วันที่คาดว่ายาจะหมด คำนวณจากสิ่งที่คุณกรอก:\n\n"
            "    จำนวนวันที่ใช้ได้ = จำนวนที่ให้ / ขนาดต่อวัน\n"
            "    วันที่ยาหมด = วันเริ่ม + จำนวนวันที่ใช้ได้\n\n"
            "ตัวอย่าง: ยา 10 เม็ด กินวันละ 2 เม็ด = 5 วัน\n\n"
            "เป็นการประมาณโดยสมมติว่ากินยาตามที่แพทย์สั่ง "
            "รายการติดตามผลจะแสดงผู้ป่วยที่เลยวันคาดว่ายาหมดแล้ว "
            "เพื่อจะได้โทรไปติดตาม"),
    },
}


def help_text(key):
    """Return (title, body) for a help pop-up in the current language."""
    entry = HELP[key]
    if _lang == "th":
        return entry["th_title"], entry["th"]
    return entry["en_title"], entry["en"]
