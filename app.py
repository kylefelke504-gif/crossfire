from flask import Flask, render_template, request
import requests
import re
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


def parse_price(price_str):
    if not price_str:
        return 0.0
    
    price_str_raw = str(price_str).strip()

    # 1. KIỂM TRẢ TIỀN VIỆT (Chứa chữ 'đ', '₫', 'vnd' HOẶC có mệnh giá >= 500)
    is_vnd = any(k in price_str_raw.lower() for k in ['đ', '₫', 'vnd'])
    
    # Lấy toàn bộ số nguyên để kiểm tra mệnh giá
    digits = re.sub(r'[^0-9]', '', price_str_raw)
    num_val = float(digits) if digits else 0.0

    if is_vnd or num_val >= 500:
        # Nếu là tiền Việt, lấy tổng số tiền VNĐ chia cho tỷ giá ra USD
        return round(num_val / VND_TO_USD_RATE, 2)

    # 2. XỬ LÝ TIỀN USD (Dạng "2,99 US$", "$0.10", "0,49 US$")
    clean_str = re.sub(r'[^0-9.,]', '', price_str_raw).strip()
    if ',' in clean_str:
        clean_str = clean_str.replace(',', '.')
    try:
        return float(clean_str)
    except ValueError:
        return 0.0


def fetch_api(url, user, start_date, end_date, start_time, end_time):
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

    except Exception as e:
        print(f"API ERROR [{user}]:", e)
        data = []

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
