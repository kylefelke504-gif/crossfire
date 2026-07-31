from flask import Flask, render_template, request
import requests
import re
from collections import defaultdict
from datetime import datetime, timedelta

app = Flask(__name__)

# ===== KHAI BÁO CÁC LINK & USER =====
URL_BASE = "https://crossfirelegend.xyz/gambler/user/child/statistic"

# Cấu hình User (Đã sửa USER6)
USER1 = "a7"
USER2 = "a8"
USER3 = "a9"
USER4 = "a4"
USER5 = "a5"
USER6 = "a6"  # <--- ĐÃ SỬA: Đổi tên thành USER6


def parse_price(price_str):
    """
    Xử lý chuẩn xác giá tiền từ API (Ví dụ: "0,49 US$", "2,99 US$", "0,09 US$")
    """
    if not price_str:
        return 0.0
    
    clean_str = re.sub(r'[^0-9.,]', '', str(price_str)).strip()
    
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

        r = requests.post(url, json=payload, headers=headers, timeout=15)
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

    # ===== GỌI API CHO 6 VÍ =====
    result1, total1 = fetch_api(URL_BASE, USER1, start_date, end_date, start_time, end_time)
    result2, total2 = fetch_api(URL_BASE, USER2, start_date, end_date, start_time, end_time)
    result3, total3 = fetch_api(URL_BASE, USER3, start_date, end_date, start_time, end_time)
    result4, total4 = fetch_api(URL_BASE, USER4, start_date, end_date, start_time, end_time)
    result5, total5 = fetch_api(URL_BASE, USER5, start_date, end_date, start_time, end_time)
    result6, total6 = fetch_api(URL_BASE, USER6, start_date, end_date, start_time, end_time)  # <--- ĐÃ SỬA: USER6

    # Tính tổng tiền tất cả ví
    grand_total = total1 + total2 + total3 + total4 + total5 + total6

    return render_template(
        "index.html",

        # Ví 1
        result=result1,
        total=total1,

        # Ví 2 
        result2=result2,
        total2=total2,

        # Ví 3
        result3=result3,
        total3=total3,

        # Ví 4
        result4=result4,
        total4=total4,

        # Ví 5
        result5=result5,
        total5=total5,

        # Ví 6
        result6=result6,
        total6=total6,

        grand_total=grand_total,

        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
