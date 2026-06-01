import os
import requests
import time
import subprocess
import re
from datetime import datetime
import pytz

# --- CẤU HÌNH GIAO DIỆN ---
RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, RESET = '\033[91m', '\033[92m', '\033[93m', '\033[94m', '\033[95m', '\033[96m', '\033[0m'
CONFIG_FILE = "config.txt"
USER_AGENT = "Mozilla/5.0 (iPad; CPU OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1"

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

# --- HÀM LƯU/ĐỌC FILE TXT ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def save_config(token):
    clean_token = token.replace("Bearer ", "").strip()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(clean_token)

# --- XỬ LÝ LINK FACEBOOK ---
def extract_id_from_link(link):
    match = re.search(r'id=(\d+)', link)
    if match:
        return match.group(1)
    return link.strip()

# --- CÁC HÀM API ---
def get_accounts(token):
    token_clean = token.replace("Bearer ", "").strip()
    url = "https://gateway.golike.net/api/fb-account?limit=200"
    headers = {"Authorization": f"Bearer {token_clean}", "User-Agent": USER_AGENT}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json().get("data", [])
        return data.get("data", []) if isinstance(data, dict) else data
    except: return []

def fetch_job(token, acc_id):
    token_clean = token.replace("Bearer ", "").strip()
    url = "https://gateway.golike.net/api/advertising/publishers/get-jobs-2026"
    params = {"fb_id": acc_id, "server": "sv2", "low_job": "1"}
    headers = {"Authorization": f"Bearer {token_clean}", "User-Agent": USER_AGENT}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        jobs = res.json().get("data", [])
        return jobs[0] if jobs else None
    except: return None

def report_job(token, acc_id, job_id):
    token_clean = token.replace("Bearer ", "").strip()
    url = "https://gateway.golike.net/api/advertising/publishers/complete-jobs-2026"
    headers = {"Authorization": f"Bearer {token_clean}", "Content-Type": "application/json"}
    payload = {"uid": acc_id, "job_id": job_id}
    try:
        return requests.post(url, headers=headers, json=payload, timeout=10).json()
    except: return None

# --- VÒNG LẶP CÀY JOB ---
def start_job_loop(token, acc):
    acc_id = str(acc.get("fb_id"))
    name = acc.get("name") or acc.get("fb_name") or "Không tên"
    print(f"\n{YELLOW}[!] Bắt đầu cày cho: {name} | UID: {acc_id}{RESET}")
    
    empty_job_count = 0
    while True:
        job = fetch_job(token, acc_id)
        if not job:
            empty_job_count += 1
            for i in range(15, 0, -1):
                print(f"{CYAN}[🔎] Không có job, thử lại sau {i}s ({empty_job_count}/3){RESET}", end='\r')
                time.sleep(1)
            if empty_job_count >= 3:
                print(f"\n{RED}[!] Hết job, quay về menu chính...{RESET}")
                return 
            continue
        
        empty_job_count = 0
        job_type = job.get("type", "JOB").upper()
        print(f"\n{GREEN}[!] CÓ JOB MỚI: {job_type}{RESET}")
        print(f"{YELLOW} -> Link: {job.get('link')}{RESET}")
        
        print(f"{CYAN}[⏳] Đang chờ 3 giây trước khi mở link...{RESET}")
        time.sleep(3)
        
        subprocess.run(['am', 'start', '-a', 'android.intent.action.VIEW', '-d', job.get('link')], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        input(f"{MAGENTA}[?] Làm xong, nhấn [ENTER] để nhận xu...{RESET}")
        
        res = report_job(token, acc_id, job.get("id"))
        if res and res.get("success"):
            print(f"{GREEN}[+] Thành công! {res.get('message')}{RESET}")
        else:
            print(f"{RED}[!] Báo cáo thất bại!{RESET}")
        time.sleep(2)

# --- HÀM CHÍNH ---
def main():
    saved_token = load_config()
    token = None
    print_banner()
    
    if saved_token:
        print(f"{GREEN}[1] Dùng Token đã lưu{RESET}")
        print(f"{YELLOW}[2] Nhập Token mới{RESET}")
        choice = input(f"{CYAN}[?] Lựa chọn (1/2): {RESET}").strip()
        if choice == '1': token = saved_token
        else:
            token = input(f"{YELLOW}[+] Nhập Token mới: {RESET}").strip()
            save_config(token)
    else:
        token = input(f"{YELLOW}[+] Chưa có token, hãy nhập Token: {RESET}").strip()
        save_config(token)

    while True:
        accounts = get_accounts(token)
        if not accounts:
            print(f"{RED}[!] Không lấy được tài khoản, Token sai hoặc hết hạn!{RESET}")
            break

        print(f"\n{CYAN}{'STT':<5} | {'NAME':<15} | {'UID':<18} | {'STATUS'}{RESET}")
        print("-" * 65)
        
        live_list = []
        stt = 1
        for acc in accounts:
            name = acc.get("name") or acc.get("fb_name") or "Không tên"
            display_name = f"{CYAN}{str(name)[:15]:<15}{RESET}" 
            is_live = acc.get("is_active") or acc.get("status")
            status = f"{GREEN}LIVE{RESET}" if is_live else f"{RED}CHECKPOINT{RESET}"
            
            print(f"{str(stt):<5} | {display_name} | {str(acc.get('fb_id')):<18} | {status}")
            if is_live: live_list.append({"stt": stt, "data": acc})
            stt += 1
                
        choice = input(f"\n{YELLOW}[?] Nhập STT, UID hoặc Link profile: {RESET}").strip()
        if not choice: break
        
        target = extract_id_from_link(choice)
        selected_acc = None
        
        if target.isdigit() and len(target) < 4:
            item = next((x for x in live_list if x["stt"] == int(target)), None)
            if item: selected_acc = item["data"]
        
        if not selected_acc:
            selected_acc = next((a["data"] for a in live_list if str(a["data"].get('fb_id')) == target), None)
        
        if selected_acc: start_job_loop(token, selected_acc)
        else:
            print(f"{RED}[!] Không tìm thấy tài khoản tương ứng: {target}{RESET}")
            time.sleep(1)

if __name__ == "__main__":
    main()
