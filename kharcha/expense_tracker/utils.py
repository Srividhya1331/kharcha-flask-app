"""Small, pure helper functions (easy to unit test)."""
import secrets
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import session

MAX_AMOUNT_RUPEES = Decimal("10000000")  # ₹1 crore per expense is a sane upper bound


# ---------- money ----------
# Money is stored as integer paise. Floats cannot represent 0.1 exactly,
# so summing float rupees drifts; integers never do.
def parse_amount_to_paise(raw):
    """'1,250.50' -> 125050. Raises ValueError with a user-friendly message."""
    text = (raw or "").strip().replace(",", "")
    if not text:
        raise ValueError("Enter an amount.")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError("Amount must be a number, like 450 or 450.50.") from None
    if not value.is_finite():
        raise ValueError("Amount must be a number, like 450 or 450.50.")
    if value <= 0:
        raise ValueError("Amount must be greater than zero.")
    if value > MAX_AMOUNT_RUPEES:
        raise ValueError("Amount is too large.")
    if value != value.quantize(Decimal("0.01")):
        raise ValueError("Use at most two decimal places.")
    return int(value * 100)


def paise_to_str(paise):
    """125050 -> '1250.50' (for form fields and JSON)."""
    rupees, rem = divmod(paise, 100)
    return f"{rupees}.{rem:02d}"


def format_inr(paise):
    """Indian digit grouping: 12345678 paise -> '₹1,23,456.78'."""
    rupees, rem = divmod(abs(paise), 100)
    digits = str(rupees)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    sign = "-" if paise < 0 else ""
    return f"{sign}₹{digits}.{rem:02d}"


# ---------- months ('YYYY-MM' strings) ----------
def current_month():
    return date.today().strftime("%Y-%m")


def parse_month(value):
    """Return a valid 'YYYY-MM' string or None."""
    try:
        return datetime.strptime(value or "", "%Y-%m").strftime("%Y-%m")
    except ValueError:
        return None


def month_bounds(month):
    """Half-open range [start, end) so December rolls into January correctly."""
    year, mon = map(int, month.split("-"))
    start = date(year, mon, 1)
    end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
    return start, end


def shift_month(month, delta):
    year, mon = map(int, month.split("-"))
    index = year * 12 + (mon - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_label(month, short=False):
    return datetime.strptime(month, "%Y-%m").strftime("%b" if short else "%b %Y")


# ---------- security ----------
def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def csv_safe(value):
    """Stop spreadsheet formula injection when a CSV is opened in Excel."""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def is_safe_redirect(target):
    """Only allow same-site relative paths (prevents open redirects)."""
    return bool(target) and target.startswith("/") and not target.startswith("//")
