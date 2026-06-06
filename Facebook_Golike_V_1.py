import os
import requests
import time
import subprocess
import re
import json
import base64
from datetime import datetime
import pytz

# --- CẤU HÌNH GIAO DIỆN ---
RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, RESET = '\033[91m', '\033[92m', '\033[93m', '\033[94m', '\033[95m', '\033[96m', '\033[0m'
CONFIG_FILE = "config.txt"
MAP_FILE = "mapping.json"
ERROR_FILE = "error_jobs.txt"

# User-Agent đồng bộ hệ thống di động Android sạch
USER_AGENT = "Mozilla/5.0 (iPad; CPU OS 18_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1"

# Khóa thiết bị cứng lấy từ phiên đăng nhập cố định của bạn
G_DEVICE_ID = "9f7b42b3-d67b-4b2e-b9f8-869398af4406"
G_AUTH = "Pk57G4Q9LupnhDuVtTTfF3oAg6qbXMc2keje2uG4GCVMsc0YcMKMeE2el8tousb_yrDZ5lhKz6FgZn3eD3k-8NoZGpwlRjT9QOmRySCKRv5aE9Uipl-Ghoeb84xcG-6eAAR7JCF45RLLWfG7gk0q4ydMYjjAxOozses99nkrRRykGhdeO2ZLejvqlcXUdUSOpkcIkxf0itdm8b9ihZvixCkKR5KwM-rfsZ0DhWZ0HTYK9CyMt8CAlLkDXO_wafxlYQ-5qw1matV0wt3Ot40Ni-LR0QINt497f0CY9lijPv8efXLg6RSByS25B-ZACXc2SnGjbuYR8j5-E45E_wo2rvWZOLCSDHZcNCblRJlXDgfWCWgM"

# --- HÀM TẠO THAM SỐ `t` ĐỘNG THEO THỜI GIAN THỰC ---
def generate_t_param():
    """
    Tự động lấy timestamp hiện tại (mili giây), mã hóa Base64 hai lần
    để khớp hoàn toàn với cơ chế sinh chữ ký động của hệ thống Golike 2026.
    """
    millis = str(int(time.time() * 1000))
    # Mã hóa lần 1
    b1 = base64.b64encode(millis.encode('utf-8')).decode('utf-8')
    # Mã hóa lần 2
    b2 = base64.b64encode(b1.encode('utf-8')).decode('utf-8')
    return b2

# --- HÀM TẠO HEADERS ĐỒNG BỘ ---
def get_base_headers(token, dynamic_t):
    token_clean = token.replace("Bearer ", "").strip()
    return {
        "Authorization": f"Bearer {token_clean}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=utf-8",
        "t": dynamic_t,
        "g-device-id": G_DEVICE_ID,
        "g-auth": G_AUTH,
        "Origin": "https://app.golike.net",
        "Referer": "https://app.golike.net/"
    }

# --- HÀM MAPPING & JOB LỖI ---
def load_map():
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, "r") as f: return json.load(f)
    return {}

def save_map(data):
    with open(MAP_FILE, "w") as f: json.dump(data, f, indent=4)

def get_browser_for_acc(uid):
    mapping = load_map()
    if uid in mapping: return mapping[uid]
    print(f"\n{YELLOW}[!] Tài khoản {uid} chưa được gán trình duyệt!{RESET}")
    pkg = input(f"{CYAN}[+] Dán Package Name (VD: mark.via.gq): {RESET}").strip()
    mapping[uid] = pkg
    save_map(mapping)
    return pkg

def save_skip_job(job_id):
    with open(ERROR_FILE, "a") as f: f.write(f"{job_id}\n")

def is_job_error(job_id):
    if not os.path.exists(ERROR_FILE): return False
    with open(ERROR_FILE, "r") as f:
        return str(job_id) in f.read().splitlines()

# --- CÁC HÀM TIỆN ÍCH ---
def get_vn_time():
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    return datetime.now(vn_tz).strftime('%d/%m/%Y %H:%M:%S')

def get_public_ip():
    try: return requests.get("https://api.ipify.org", timeout=5).text
    except: return "Không xác định"

def print_banner():
    print(f"""
{MAGENTA}╔═════════════════════════════════════════════╗
{CYAN}║                BANNER: TINH 89              ║
{MAGENTA}╚═════════════════════════════════════════════╝
{YELLOW} 🕒 Giờ VN: {get_vn_time()}
{GREEN} 🌐 IP Mạng: {get_public_ip()}
{MAGENTA}───────────────────────────────────────────────{RESET}""")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f: return f.read().strip()
    return ""

def save_config(token):
    clean_token = token.replace("Bearer ", "").strip()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f: f.write(clean_token)

def extract_id_from_link(link):
    match = re.search(r'id=(\d+)', link)
    return match.group(1) if match else link.strip()

def get_accounts(token):
    dynamic_t = generate_t_param()
    url = "https://gateway.golike.net/api/fb-account?limit=200"
    headers = get_base_headers(token, dynamic_t)
    try:
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json().get("data", [])
        return data.get("data", []) if isinstance(data, dict) else data
    except: return []

# --- GIAO TIẾP API LẤY JOB VỚI CHỮ KÝ ĐỘNG ---

def fetch_job(token, acc_id):
    """Lấy danh sách job bằng việc sinh mã t mới liên tục chống lệch giờ trên Gateway"""
    dynamic_t = generate_t_param()
    url = "https://gateway.golike.net/api/advertising/publishers/get-jobs-2026"
    
    params = {
        "fb_id": acc_id, 
        "server": "sv2", 
        "low_job": "1"
    }
    
    headers = get_base_headers(token, dynamic_t)
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res_json = res.json()
        
        if not res_json.get("success"):
            # In ra thông báo hệ thống nếu bị từ chối nhận job
            print(f"\n{RED}[X] Golike Từ Chối Trả Job! Chi tiết: {res_json.get('message', 'Không rõ nguyên do')}{RESET}")
            
        return res_json.get("data", [])
    except Exception as e: 
        return []

def report_job(token, acc_id, job_id):
    dynamic_t = generate_t_param()
    url = "https://gateway.golike.net/api/advertising/publishers/complete-jobs-2026"
    
    headers = get_base_headers(token, dynamic_t)
    payload = {"uid": acc_id, "job_id": job_id}
    try: return requests.post(url, headers=headers, json=payload, timeout=10).json()
    except: return None

def skip_job(token, acc_id, ads_id):
    dynamic_t = generate_t_param()
    url = "https://gateway.golike.net/api/report/send"
    
    headers = get_base_headers(token, dynamic_t)
    payload = {"description": "Lỗi hệ thống", "users_advertising_id": ads_id, "type": "ads", "fb_id": acc_id, "error_type": 0, "provider": "facebook", "comment": None}
    try: return requests.post(url, headers=headers, json=payload, timeout=10).json()
    except: return None

# --- VÒNG LẶP CÀY JOB THẾ HỆ MỚI ---
def start_job_loop(token, acc):
    acc_id = str(acc.get("fb_id"))
    pkg = get_browser_for_acc(acc_id)
    name = acc.get("name") or acc.get("fb_name") or "Không tên"
    print(f"\n{YELLOW}[!] Bắt đầu cày cho: {name} | Trình duyệt: {pkg}{RESET}")
    
    empty_job_count = 0
    while True:
        job_list = fetch_job(token, acc_id)
        
        # Nếu danh sách rỗng (hết job hoặc đang lỗi phân phối)
        if not job_list or len(job_list) == 0:
            empty_job_count += 1
            for i in range(15, 0, -1):
                print(f"{CYAN}[🔎] Không có job, thử lại sau {i}s ({empty_job_count}/3){RESET}", end='\r')
                time.sleep(1)
            if empty_job_count >= 3:
                print(f"\n{RED}[!] Không lấy được job, quay về menu chính...{RESET}")
                return 
            continue
        
        empty_job_count = 0
        
                # Duyệt tuần tự mảng danh sách công việc
        for job in job_list:
            if is_job_error(job.get("id")):
                print(f"{YELLOW}[!] Job {job.get('id')} thuộc danh sách đen, đang bỏ qua...{RESET}")
                continue
            
            job_type = str(job.get('type') or 'JOB').upper()
            reaction = str(job.get('reaction') or 'LIKE').upper()
            
            print(f"\n{GREEN}[!] CÓ JOB MỚI: {job_type} ({reaction}){RESET}")


            
            print(f"\n{GREEN}[!] CÓ JOB MỚI: {job_type} ({reaction}){RESET}")
            print(f"{YELLOW} -> Link: {job.get('link')}{RESET}")
            
            print(f"{CYAN}[⏳] Đang đợi 2 giây để load trình duyệt...{RESET}")
            time.sleep(2) 
            
            subprocess.run(['am', 'start', '-n', f'{pkg}/mark.via.Shell', '-a', 'android.intent.action.VIEW', '-d', job.get('link')], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            cmd = input(f"{MAGENTA}[?] Đã tương tác `{reaction}` xong [ENTER] | [x] Báo lỗi: {RESET}").strip().lower()
            
            if cmd == 'x':
                print(f"{RED}[!] Đang lưu Job lỗi và thông báo hệ thống...{RESET}")
                save_skip_job(job.get("id"))
                ads_id = job.get("users_advertising_id") or job.get("id")
                skip_job(token, acc_id, ads_id)
                time.sleep(2) 
            else:
                res = report_job(token, acc_id, job.get("id"))
                if res and res.get("success"):
                    print(f"{GREEN}[+] {res.get('message')}{RESET}")
                else:
                    print(f"{RED}[!] Báo cáo thất bại!{RESET}")
            
            time.sleep(3)

def main():
    # Sử dụng Token Bearer mới bạn trích xuất từ dữ liệu Header của bạn
    static_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOlwvXC9nYXRld2F5LmdvbGlrZS5uZXRcL2FwaVwvbG9naW4iLCJpYXQiOjE3ODA0NTU4MzUsImV4cCI6MTgxMTk5MTgzNSwibmJmIjoxNzgwNDU1ODM1LCJqdGkiOiIxOFNXQjBucjludE1DN3ltIiwic3ViIjoyNTIzMjcyLCJwcnYiOiJiOTEyNzk5NzhmMTFhYTdiYzU2NzA0ODdmZmYwMWUyMjgyNTNmZTQ4In0.obnwhjp-y2EjYfzPi9Os42HsUtuQLkiE41j8pWIZ4qo"
    save_config(static_token)
    token = static_token
    print_banner()
    
    print(f"{GREEN}[+] Đã đồng bộ Token xác thực và mã hóa thời gian thực 2026!{RESET}")
    time.sleep(1)

    while True:
        accounts = get_accounts(token)
        if not accounts: 
            print(f"{RED}[!] Không lấy được cấu trúc tài khoản. Token hoặc cụm khóa g-auth hết hạn!{RESET}")
            break
            
        print(f"\n{CYAN}{'STT':<5} | {'NAME':<15} | {'UID':<18} | {'STATUS'}{RESET}")
        print("-" * 65)
        live_list = []
        for i, acc in enumerate(accounts, 1):
            name = acc.get("name") or acc.get("fb_name") or "Không tên"
            is_live = acc.get("is_active") or acc.get("status")
            status = f"{GREEN}LIVE{RESET}" if is_live else f"{RED}CHECKPOINT{RESET}"
            print(f"{i:<5} | {str(name)[:15]:<15} | {str(acc.get('fb_id')):<18} | {status}")
            if is_live: live_list.append({"stt": i, "data": acc})
                
        choice = input(f"\n{YELLOW}[?] Nhập STT, UID hoặc Link profile để chạy: {RESET}").strip()
        if not choice: break
        target = extract_id_from_link(choice)
        selected_acc = next((a["data"] for a in live_list if str(a["stt"]) == target or str(a["data"].get('fb_id')) == target), None)
        if selected_acc: start_job_loop(token, selected_acc)
        else: print(f"{RED}[!] Không tìm thấy tài khoản hợp lệ!{RESET}"); time.sleep(1)

if __name__ == "__main__":
    main()
