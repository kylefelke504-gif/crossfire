from flask import Flask, render_template, request
import requests
import re
import os
import json
from collections import defaultdict
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# ===== KHAI BÁO CÁC LINK & USER =====
URL_BASE = "https://crossfirelegend.xyz/gambler/user/child/statistic"

USER1 = "a7"
USER2 = "a8"
USER3 = "a9"

USER4 = "a4"
USER5 = "a5"
USER6 = "a6"

# Tỷ giá 52,000 VND / 1.99 USD = 26,130.65
VND_TO_USD_RATE = 26130.65

# Tạo thư mục data để lưu trữ file dữ liệu dự phòng
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


def parse_price(price_str):
    if not price_str:
        return 0.0
    
    price_str_raw = str(price_str).strip()
    price_lower = price_str_raw.lower()

    # 1. Kiểm tra ký hiệu tiền tệ rõ ràng
    is_vnd = any(k in price_lower for k in ['đ', '₫', 'vnd', 'vnđ'])
    is_usd = any(k in price_lower for k in ['$', 'us$', 'usd'])

    # 2. XỬ LÝ TIỀN USD CHẮC CHẮN (VD: "$9.99", "1,99 US$", "$0.09")
    if is_usd:
        clean_str = re.sub(r'[^0-9.,]', '', price_str_raw).strip()
        if ',' in clean_str:
            clean_str = clean_str.replace(',', '.')
        try:
            return float(clean_str)
        except ValueError:
            return 0.0

    # 3. XỬ LÝ TIỀN VNĐ CHẮC CHẮN (VD: "50.000đ", "100,000 VNĐ")
    if is_vnd:
        digits = re.sub(r'[^0-9]', '', price_str_raw)
        num_val = float(digits) if digits else 0.0
        return round(num_val / VND_TO_USD_RATE, 2)

    # 4. TRƯỜNG HỢP KHÔNG CÓ KÝ HIỆU (VD: "9.99", "2,99", "50000")
    clean_str = re.sub(r'[^0-9.,]', '', price_str_raw).strip()
    if ',' in clean_str and '.' not in clean_str:
        clean_str = clean_str.replace(',', '.')

    try:
        val = float(clean_str)
        # Nếu số tiền gốc >= 500 thì mới coi là VNĐ, còn lại là USD
        if val >= 500:
            return round(val / VND_TO_USD_RATE, 2)
        return val
    except ValueError:
        return 0.0


def save_backup_data(user, start_date, end_date, data):
    """Hàm tự động lưu dữ liệu JSON vào folder data/"""
    try:
        filename = f"{user}_{start_date}_to_{end_date}.json"
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Lỗi khi lưu backup [{user}]:", e)


def load_backup_data(user, start_date, end_date):
    """Hàm tự động đọc lại dữ liệu từ folder data/ khi API gốc gặp sự cố"""
    try:
        filename = f"{user}_{start_date}_to_{end_date}.json"
        filepath = os.path.join(DATA_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                print(f"⚠️ [DỰ PHÒNG] Đọc dữ liệu đã lưu cho [{user}]")
                return json.load(f)
    except Exception as e:
        print(f"Lỗi khi đọc backup [{user}]:", e)
    return []


def fetch_api(url, user, start_date, end_date, start_time, end_time):
    data = []
    try:
        start_local = datetime.strptime(
            f"{start_date} {start_time}",
            "%Y-%m-%d %H:%M:%S"
        )
        end_local = datetime.strptime(
            f"{end_date} {end_time}",
            "%Y-%m-%d %H:%M:%S"
        )

        start_utc = start_local - timedelta(hours=7)
        end_utc = end_local - timedelta(hours=7)

        payload = {
            "shopId": None,
            "packageName": "",
            "assigned": user,
            "productId": "",
            "action": "import_token",
            "startDate": start_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endDate": end_utc.strftime("%Y-%m-%dT%H:%M:%S.999Z")
        }

        domain = url.split("/")[2] if "//" in url else "crossfirelegend.xyz"

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": f"https://{domain}",
            "Referer": f"https://{domain}/thong-ke-nap?user={user}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "X-Requested-With": "XMLHttpRequest"
        }

        with requests.Session() as session:
            r = session.post(url, json=payload, headers=headers, timeout=8)
            r.raise_for_status()
            res_json = r.json()

        data = res_json.get("data", []) if isinstance(res_json, dict) else []

        if data:
            save_backup_data(user, start_date, end_date, data)
        else:
            backup = load_backup_data(user, start_date, end_date)
            if backup:
                data = backup

    except Exception as e:
        print(f"API ERROR [{user}]:", e)
        data = load_backup_data(user, start_date, end_date)

    result = defaultdict(lambda: {"price": 0.0, "count": 0})
    total = 0.0

    for item in data:
        game = item.get("gameName") or item.get("title") or "Unknown"
        price = parse_price(item.get("price", "0"))
        
        try:
            count = int(item.get("count", 0))
        except (ValueError, TypeError):
            count = 0

        money = price * count

        result[game]["price"] += money
        result[game]["count"] += count
        total += money

    result = dict(
        sorted(
            result.items(),
            key=lambda x: x[1]["price"],
            reverse=True
        )
    )

    return result, total


@app.route("/")
def index():
    now = datetime.utcnow() + timedelta(hours=7)

    start_date = request.args.get("start_date") or now.strftime("%Y-%m-%d")
    end_date = request.args.get("end_date") or now.strftime("%Y-%m-%d")

    start_time = request.args.get("start_time") or "00:00:00"
    end_time = request.args.get("end_time") or "23:59:59"

    users = [USER1, USER2, USER3, USER4, USER5, USER6]

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [
            executor.submit(
                fetch_api, URL_BASE, u, start_date, end_date, start_time, end_time
            )
            for u in users
        ]
        results = [f.result() for f in futures]

    (result1, total1), (result2, total2), (result3, total3), \
    (result4, total4), (result5, total5), (result6, total6) = results

    group1_total = total1 + total2 + total3
    group2_total = total4 + total5 + total6
    grand_total = group1_total + group2_total

    return render_template(
        "index.html",

        result=result1, total=total1,
        result2=result2, total2=total2,
        result3=result3, total3=total3,

        result4=result4, total4=total4,
        result5=result5, total5=total5,
        result6=result6, total6=total6,

        group1_total=group1_total,
        group2_total=group2_total,
        grand_total=grand_total,

        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
