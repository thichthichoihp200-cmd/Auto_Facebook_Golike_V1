import os
import json
import requests
import time
import subprocess
from datetime import datetime
import pytz

# --- CẤU HÌNH GIAO DIỆN ---
RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, RESET = '\033[91m', '\033[92m', '\033[93m', '\033[94m', '\033[95m', '\033[96m', '\033[0m'
CONFIG_FILE = "config.json"
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

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"authorized": ""}

def save_config(token):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"authorized": token.strip()}, f, indent=4)

def get_accounts(token):
    url = "https://gateway.golike.net/api/fb-account?limit=200"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json().get("data", [])
        return data.get("data", []) if isinstance(data, dict) else data
    except: return []

def fetch_job(token, acc_id):
    url = "https://gateway.golike.net/api/advertising/publishers/get-jobs-2026"
    params = {"fb_id": acc_id, "server": "sv2", "low_job": "1"}
    headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        jobs = res.json().get("data", [])
        return jobs[0] if jobs else None
    except: return None

def report_job(token, acc_id, job_id):
    url = "https://gateway.golike.net/api/advertising/publishers/complete-jobs-2026"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"uid": acc_id, "job_id": job_id}
    try:
        return requests.post(url, headers=headers, json=payload, timeout=10).json()
    except: return None

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
        
        subprocess.run(['am', 'start', '-a', 'android.intent.action.VIEW', '-d', job.get('link')], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        input(f"{MAGENTA}[?] Làm xong, nhấn [ENTER] để nhận xu...{RESET}")
        
        res = report_job(token, acc_id, job.get("id"))
        if res and res.get("success"):
            print(f"{GREEN}[+] Thành công! {res.get('message')}{RESET}")
        else:
            print(f"{RED}[!] Báo cáo thất bại!{RESET}")
        time.sleep(2)

def main():
    config = load_config()
    token = config.get("authorized")
    if not token:
        token = input(f"{YELLOW}[+] Nhập Token Authorized: {RESET}").strip()
        save_config(token)
    
    while True:
        print_banner()
        accounts = get_accounts(token)
        if not accounts:
            print(f"{RED}[!] Không lấy được tài khoản!{RESET}")
            break

                # In tiêu đề bảng mới
        print(f"{CYAN}{'STT':<5} | {'NAME':<15} | {'UID':<18} | {'STATUS'}{RESET}")
        print("-" * 65)
        
        live_list = []
        stt = 1
        for acc in accounts:
            name = acc.get("name") or acc.get("fb_name") or "Không tên"
            is_live = acc.get("is_active") or acc.get("status")
            status = f"{GREEN}LIVE{RESET}" if is_live else f"{RED}CHECKPOINT{RESET}"
            
            # Thứ tự in: STT - NAME - UID - STATUS
            print(f"{str(stt):<5} | {str(name):<15} | {str(acc.get('fb_id')):<18} | {status}")
            
            if is_live:
                live_list.append({"stt": stt, "data": acc})
            stt += 1
                
        choice = input(f"\n{YELLOW}[?] Nhập STT hoặc UID để cày (Enter để thoát): {RESET}").strip()
        if not choice: break
        
        selected_acc = None
        if choice.isdigit():
            item = next((x for x in live_list if x["stt"] == int(choice)), None)
            if item: selected_acc = item["data"]
        else:
            selected_acc = next((a["data"] for a in live_list if str(a["data"].get('fb_id')) == choice), None)
        
        if selected_acc: start_job_loop(token, selected_acc)
        else:
            print(f"{RED}[!] Lựa chọn không hợp lệ!{RESET}")
            time.sleep(1)

if __name__ == "__main__":
    main()
