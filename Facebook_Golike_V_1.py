import os
import requests
import time
import subprocess
import re
import json
import base64
from datetime import datetime
import pytz
import random
import threading
from queue import Queue  # Bổ sung Queue để quản lý danh sách acc tự động đổi

# --- CẤU HÌNH GIAO DIỆN ---
RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, RESET = '\033[91m', '\033[92m', '\033[93m', '\033[94m', '\033[95m', '\033[96m', '\033[0m'
CONFIG_FILE = "config.txt"
MAP_FILE = "mapping.json"
ERROR_FILE = "error_jobs.txt"

# Lock dùng để đồng bộ hóa việc in ấn, tránh tranh chấp màn hình giữa các luồng
print_lock = threading.Lock()

# User-Agent đồng bộ hệ thống di động Android sạch
USER_AGENT = "Mozilla/5.0 (iPad; CPU OS 18_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1"

# Khóa thiết bị cứng lấy từ phiên đăng nhập cố định của bạn
G_DEVICE_ID = "9f7b42b3-d67b-4b2e-b9f8-869398af4406"
G_AUTH = "Pk57G4Q9LupnhDuVtTTfF3oAg6qbXMc2keje2uG4GCVMsc0YcMKMeE2el8tousb_yrDZ5lhKz6FgZn3eD3k-8NoZGpwlRjT9QOmRySCKRv5aE9Uipl-Ghoeb84xcG-6eAAR7JCF45RLLWfG7gk0q4ydMYjjAxOozses99nkrRRykGhdeO2ZLejvqlcXUdUSOpkcIkxf0itdm8b9ihZvixCkKR5KwM-rfsZ0DhWZ0HTYK9CyMt8CAlLkDXO_wafxlYQ-5qw1matV0wt3Ot40Ni-LR0QINt497f0CY9lijPv8efXLg6RSByS25B-ZACXc2SnGjbuYR8j5-E45E_wo2rvWZOLCSDHZcNCblRJlXDgfWCWgM"

# Biến toàn cục lưu cấu hình delay
DELAY_MIN = 2
DELAY_MAX = 5

# Hàng đợi chứa các tài khoản để các luồng tự động lấy ra chạy
account_queue = Queue()

# --- HÀM TẠO THAM SỐ `t` ĐỘNG THEO THỜI GIAN THỰC ---
def generate_t_param():
    millis = str(int(time.time() * 1000))
    b1 = base64.b64encode(millis.encode('utf-8')).decode('utf-8')
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
    with print_lock:
        mapping = load_map()
        if uid in mapping: return mapping[uid]
        print(f"\n{YELLOW}[!] Tài khoản {uid} chưa được gán trình duyệt!{RESET}")
        pkg = input(f"{CYAN}[+] Dán Package Name (VD: mark.via.gq): {RESET}").strip()
        mapping[uid] = pkg
        save_map(mapping)
        return pkg

def save_skip_job(job_id):
    with print_lock:
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
{CYAN}║         BANNER: TINH 89 (AUTO SWITCH v3)    ║
{MAGENTA}╚═════════════════════════════════════════════╝
{YELLOW} 🕒 Giờ VN: {get_vn_time()}
{GREEN} 🌐 IP Mạng: {get_public_ip()}
{MAGENTA}───────────────────────────────────────────────{RESET}""")

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
    dynamic_t = generate_t_param()
    url = "https://gateway.golike.net/api/advertising/publishers/get-jobs-2026"
    params = {"fb_id": acc_id, "server": "sv2", "low_job": "1"}
    headers = get_base_headers(token, dynamic_t)
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res_json = res.json()
        if not res_json.get("success"):
            with print_lock:
                print(f"\n{RED}[X] ACC [{acc_id}] Từ chối job: {res_json.get('message', 'Không rõ nguyên do')}{RESET}")
        return res_json.get("data", [])
    except Exception: 
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

# --- LUỒNG XỬ LÝ CHẠY CHUNG CHO MULTI-THREAD ---
def worker_thread(token, thread_name):
    """Mỗi luồng sẽ liên tục lấy acc từ hàng đợi ra cày, hết job sẽ đổi acc tự động"""
    while not account_queue.empty():
        try:
            acc = account_queue.get_nowait()
        except:
            break
            
        acc_id = str(acc.get("fb_id"))
        pkg = get_browser_for_acc(acc_id)
        name = acc.get("name") or acc.get("fb_name") or "Không tên"
        
        with print_lock:
            print(f"\n{BLUE}[{thread_name}] Nhận tài khoản: {name} | Trình duyệt: {pkg}{RESET}")
        
        empty_job_count = 0
        switch_acc = False
        
        while True:
            job_list = fetch_job(token, acc_id)
            
            if not job_list or len(job_list) == 0:
                empty_job_count += 1
                for i in range(5, 0, -1):
                    with print_lock:
                        print(f"{CYAN}[🔎] [{name}] Hết job, kiểm tra lại sau {i}s ({empty_job_count}/3){RESET}", end='\r')
                    time.sleep(1)
                if empty_job_count >= 3:
                    with print_lock:
                        print(f"\n{RED}[!] [{name}] Đã hết sạch Job. Luồng tự động đổi tài khoản mới...{RESET}")
                    switch_acc = True
                    break
                continue
            
            empty_job_count = 0
            
            for job in job_list:
                if is_job_error(job.get("id")):
                    continue
                
                job_type = str(job.get('type') or 'JOB').upper()
                reaction = str(job.get('reaction') or 'LIKE').upper()
                
                with print_lock:
                    print(f"\n{GREEN}[!] [{thread_name}] -> ACC [{name}] CÓ JOB MỚI: {job_type} ({reaction}){RESET}")
                    print(f"{YELLOW} -> Link: {job.get('link')}{RESET}")
                
                # Tính delay ngẫu nhiên theo cấu hình người dùng nhập vào
                current_delay = random.randint(DELAY_MIN, DELAY_MAX)
                with print_lock:
                    print(f"{CYAN}[⏳] Đang đợi ngẫu nhiên {current_delay} giây...{RESET}")
                time.sleep(current_delay) 
                
                # Gọi lệnh mở Android shell
                subprocess.run(['am', 'start', '-n', f'{pkg}/mark.via.Shell', '-a', 'android.intent.action.VIEW', '-d', job.get('link')], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                with print_lock:
                    cmd = input(f"{MAGENTA}[?] [{name}] Hoàn thành ấn [ENTER] | Nhập [x] báo lỗi: {RESET}").strip().lower()
                
                if cmd == 'x':
                    with print_lock:
                        print(f"{RED}[!] Đang lưu báo lỗi job...{RESET}")
                    save_skip_job(job.get("id"))
                    ads_id = job.get("users_advertising_id") or job.get("id")
                    skip_job(token, acc_id, ads_id)
                    time.sleep(2) 
                else:
                    res = report_job(token, acc_id, job.get("id"))
                    with print_lock:
                        if res and res.get("success"):
                            print(f"{GREEN}[+] [{name}] {res.get('message')}{RESET}")
                        else:
                            print(f"{RED}[!] [{name}] Báo cáo thất bại!{RESET}")
                
                time.sleep(3)
        
        # Đánh dấu đã xử lý xong tài khoản cũ để chuyển sang tài khoản kế tiếp trong Queue
        account_queue.task_done()

def main():
    global DELAY_MIN, DELAY_MAX
    static_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOlwvXC9nYXRld2F5LmdvbGlrZS5uZXRcL2FwaVwvbG9naW4iLCJpYXQiOjE3ODA0NTU4MzUsImV4cCI6MTgxMTk5MTgzNSwibmJmIjoxNzgwNDU1ODM1LCJqdGkiOiIxOFNXQjBucjludE1DN3ltIiwic3ViIjoyNTIzMjcyLCJwcnYiOiJiOTEyNzk5NzhmMTFhYTdiYzU2NzA0ODdmZmYwMWUyMjgyNTNmZTQ4In0.obnwhjp-y2EjYfzPi9Os42HsUtuQLkiE41j8pWIZ4qo"
    save_config(static_token)
    token = static_token
    print_banner()
    
    print(f"{GREEN}[+] Khởi chạy và đồng bộ hóa API Golike 2026 thành công!{RESET}")
    
    # --- CẤU HÌNH THỜI GIAN DELAY JOB ---
    try:
        print(f"\n{CYAN}--- CÀI ĐẶT THỜI GIAN DELAY LÀM JOB ---{RESET}")
        DELAY_MIN = int(input(f"{YELLOW}[+] Nhập delay tối thiểu (s) [Mặc định 2]: {RESET}") or 2)
        DELAY_MAX = int(input(f"{YELLOW}[+] Nhập delay tối đa (s) [Mặc định 5]: {RESET}") or 5)
        if DELAY_MIN > DELAY_MAX:
            DELAY_MIN, DELAY_MAX = DELAY_MAX, DELAY_MIN
    except ValueError:
        DELAY_MIN, DELAY_MAX = 2, 5
    print(f"{GREEN}[✓] Đã lưu cấu hình delay ngẫu nhiên: {DELAY_MIN}s -> {DELAY_MAX}s{RESET}")

    while True:
        accounts = get_accounts(token)
        if not accounts: 
            print(f"{RED}[!] Không lấy được cấu trúc tài khoản. Token hết hạn!{RESET}")
            break
            
        print(f"\n{CYAN}{'STT':<5} | {'NAME':<15} | {'UID':<18} | {'STATUS'}{RESET}")
        print("-" * 65)
        live_list = []
        for i, acc in enumerate(accounts, 1):
            name = acc.get("name") or acc.get("fb_name") or "Không tên"
            is_live = acc.get("is_active") or acc.get("status")
            status = f"{GREEN}LIVE{RESET}" if is_live else f"{RED}CHECKPOINT{RESET}"
            print(f"{i:<5} | {str(name)[:15]:<15} | {str(acc.get('fb_id')):<18} | {status}")
            if is_live: live_list.append(acc)
                
        print(f"\n{YELLOW}[⚙️] CHẾ ĐỘ ĐA LUỒNG TỰ ĐỘNG ĐỔI ACC KHI HẾT JOB{RESET}")
        print(f"{CYAN}[!] Tổng số tài khoản sẵn sàng chạy: {len(live_list)}{RESET}")
        run_confirm = input(f"{YELLOW}[?] Ấn [ENTER] để đưa tất cả acc LIVE vào hàng đợi chạy 2 luồng song song, hoặc gõ 'q' để thoát: {RESET}").strip().lower()
        
        if run_confirm == 'q':
            break

        # Làm sạch hàng đợi và đẩy toàn bộ danh sách acc LIVE vào Queue
        while not account_queue.empty():
            account_queue.get()
            
        for acc in live_list:
            account_queue.put(acc)

        if len(live_list) == 0:
            print(f"{RED}[!] Không có tài khoản LIVE nào khả dụng!{RESET}")
            time.sleep(2)
            continue

        # Tạo và khởi chạy song song 2 luồng (Luồng A và Luồng B)
        t1 = threading.Thread(target=worker_thread, args=(token, "LUỒNG A"), daemon=True)
        t2 = threading.Thread(target=worker_thread, args=(token, "LUỒNG B"), daemon=True)

        print(f"\n{GREEN}[▶] Đang phân bổ tài khoản và khởi động 2 luồng song song...{RESET}")
        t1.start()
        # Chờ 2 giây để luồng 1 mở trình duyệt ổn định rồi mới mở luồng 2, tránh nghẽn thiết bị
        time.sleep(2) 
        if account_queue.qsize() > 0:
            t2.start()

        # Chờ cả 2 luồng tiêu thụ hết hàng đợi các tài khoản rồi mới trả về giao diện chính
        if t1.is_alive(): t1.join()
        if t2.is_alive(): t2.join()
        
        print(f"\n{GREEN}[✓] Toàn bộ tài khoản trong hàng đợi đã xử lý xong hoặc hết job!{RESET}")
        input(f"{YELLOW}[?] Nhấn ENTER để tải lại danh sách tài khoản...{RESET}")

if __name__ == "__main__":
    main()
