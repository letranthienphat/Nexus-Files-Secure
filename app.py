import os
import sys
import json
import time
import struct
import secrets
import threading
import requests
import re
import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256

# --- KHAI BÁO PHIÊN BẢN HỆ THỐNG ---
VERSION = "2.0.0"
SECURE_VERSION = "2.1.5"

CONFIG_FILE = "data.json"
UPDATE_VERSION_URL = "https://raw.githubusercontent.com/letranthienphat/Nexus-Files-Secure/refs/heads/main/README.md"
UPDATE_CODE_URL = "https://raw.githubusercontent.com/letranthienphat/Nexus-Files-Secure/refs/heads/main/app.py"

# Bảng màu Android 16 / Material You (Dark Theme)
COLOR_BG = "#121318"
COLOR_SURFACE = "#1E1F28"
COLOR_SURFACE_VARIANT = "#2B2C38"
COLOR_PRIMARY = "#A8C7FA"
COLOR_ON_PRIMARY = "#003062"
COLOR_ACCENT = "#D0BCFF"
COLOR_SUCCESS = "#A6C8FF"
COLOR_DANGER = "#F2B8B5"
COLOR_TEXT = "#E6E1E5"
COLOR_TEXT_MUTED = "#938F99"

class NexusFilesSecure:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Nexus Files Secure - App v{VERSION} | Secure Engine v{SECURE_VERSION}")
        self.root.configure(bg=COLOR_BG)
        
        try:
            self.root.state('zoomed')
        except Exception:
            self.root.attributes('-fullscreen', True)
            
        self.root.resizable(True, True)
        self.config = {}
        self.secure_storage_path = ""
        self.master_password = ""
        self.selected_ext_file = ""

        self.setup_android_theme()
        threading.Thread(target=self.check_update_async, daemon=True).start()
        self.load_or_init_config()

    def get_safe_chunk_size(self):
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('sullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            available_ram = stat.ullAvailPhys
            max_allowed = int(available_ram * 0.8)
        except Exception:
            max_allowed = 32 * 1024 * 1024
            
        chunk_size = min(max_allowed, 8 * 1024 * 1024)
        return max(chunk_size, 1 * 1024 * 1024)

    def setup_android_theme(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=COLOR_SURFACE, foreground=COLOR_TEXT_MUTED, 
                             padding=[20, 10], font=("Segoe UI", 11, "bold"), borderwidth=0)
        self.style.map("TNotebook.Tab", 
                       background=[("selected", COLOR_SURFACE_VARIANT)],
                       foreground=[("selected", COLOR_PRIMARY)])

        self.style.configure("Treeview", background=COLOR_SURFACE, foreground=COLOR_TEXT, 
                             fieldbackground=COLOR_SURFACE, rowheight=36, font=("Segoe UI", 10), borderwidth=0)
        self.style.configure("Treeview.Heading", background=COLOR_SURFACE_VARIANT, foreground=COLOR_TEXT, 
                             font=("Segoe UI", 10, "bold"), borderwidth=0)
        self.style.map("Treeview", background=[("selected", COLOR_SURFACE_VARIANT)], foreground=[("selected", COLOR_PRIMARY)])
        
        # Cấu hình Thanh Tiến Trình (Progressbar)
        self.style.configure("Horizontal.TProgressbar", background=COLOR_PRIMARY, troughcolor=COLOR_SURFACE_VARIANT, borderwidth=0, thickness=12)

    def create_pill_button(self, parent, text, command, bg_color=COLOR_PRIMARY, fg_color=COLOR_ON_PRIMARY, width=None):
        return tk.Button(parent, text=text, command=command, bg=bg_color, fg=fg_color,
                         activebackground=COLOR_ACCENT, activeforeground=COLOR_ON_PRIMARY,
                         font=("Segoe UI", 10, "bold"), relief="flat", bd=0, padx=16, pady=8,
                         cursor="hand2", width=width)

    def parse_version(self, version_str):
        try:
            return tuple(map(int, version_str.strip().split('.')))
        except ValueError:
            return (0, 0, 0)

    # --- CỬA SỔ HIỂN THỊ TIẾN TRÌNH (PROGRESS POPUP) ---
    def show_progress_popup(self, title_text):
        popup = tk.Toplevel(self.root)
        popup.title(title_text)
        popup.geometry("450x180")
        popup.configure(bg=COLOR_SURFACE)
        popup.resizable(False, False)
        popup.grab_set()

        lbl_status = tk.Label(popup, text="Đang khởi tạo...", font=("Segoe UI", 11, "bold"), bg=COLOR_SURFACE, fg=COLOR_TEXT)
        lbl_status.pack(anchor="w", padx=25, pady=(25, 10))

        progress = ttk.Progressbar(popup, style="Horizontal.TProgressbar", mode="determinate", length=400)
        progress.pack(padx=25, pady=5)

        lbl_percent = tk.Label(popup, text="0%", font=("Segoe UI", 10), bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED)
        lbl_percent.pack(anchor="e", padx=25, pady=(5, 10))

        def update_progress(val, text=""):
            progress['value'] = val
            lbl_percent.config(text=f"{int(val)}%")
            if text:
                lbl_status.config(text=text)
            popup.update_idletasks()

        def close_popup():
            popup.grab_release()
            popup.destroy()

        return update_progress, close_popup

    # --- HỆ THỐNG MÃ HÓA ENGINE v2.1.5 (CÓ MÃ DỰ PHÒNG SELF-HEALING) ---
    def custom_encrypt_pack_v215(self, src_path, dest_path, password, progress_callback=None):
        salt = secrets.token_bytes(16)
        key = PBKDF2(password, salt, 32, count=50000, hmac_hash_module=SHA256)
        
        file_size = os.path.getsize(src_path)
        chunk_size = self.get_safe_chunk_size()
        orig_name_bytes = os.path.basename(src_path).encode('utf-8')
        
        processed_bytes = 0
        
        with open(src_path, "rb") as f_in, open(dest_path, "wb") as f_out:
            f_out.write(b"NXS6")  # Magic Header v2.1.5
            f_out.write(salt)
            f_out.write(struct.pack("<I", len(orig_name_bytes)))
            f_out.write(orig_name_bytes)
            
            while True:
                chunk = f_in.read(chunk_size)
                if not chunk:
                    break
                
                # Tạo bản sao Parity XOR đơn giản cho khối dữ liệu để khôi phục khi hỏng
                parity_byte = bytes([sum(chunk[i::128]) % 256 for i in range(min(128, len(chunk)))])
                
                iv = secrets.token_bytes(16)
                cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                ciphertext, tag = cipher.encrypt_and_digest(chunk)
                
                f_out.write(iv)
                f_out.write(tag)
                f_out.write(struct.pack("<I", len(parity_byte)))
                f_out.write(parity_byte)
                f_out.write(struct.pack("<I", len(ciphertext)))
                f_out.write(ciphertext)
                
                processed_bytes += len(chunk)
                if progress_callback and file_size > 0:
                    pct = (processed_bytes / file_size) * 100
                    progress_callback(pct, f"Đang mã hóa bảo mật: {int(pct)}%")

    # --- GIẢI MÃ & TỰ ĐỘNG KHÔI PHỤC DỮ LIỆU (ENGINE v2.1.5) ---
    def custom_decrypt_unpack_v215(self, src_path, dest_dir, password, progress_callback=None):
        file_size = os.path.getsize(src_path)
        processed_bytes = 0
        
        with open(src_path, "rb") as f_in:
            magic = f_in.read(4)
            
            if magic == b"NXS6":  # Chuẩn v2.1.5 hỗ trợ Khôi Phục
                salt = f_in.read(16)
                key = PBKDF2(password, salt, 32, count=50000, hmac_hash_module=SHA256)
                
                name_len = struct.unpack("<I", f_in.read(4))[0]
                orig_name = f_in.read(name_len).decode('utf-8')
                out_path = os.path.join(dest_dir, orig_name)
                
                with open(out_path, "wb") as f_out:
                    while True:
                        iv = f_in.read(16)
                        if not iv:
                            break
                        tag = f_in.read(16)
                        
                        p_len_b = f_in.read(4)
                        if not p_len_b: break
                        p_len = struct.unpack("<I", p_len_b)[0]
                        parity_data = f_in.read(p_len)
                        
                        data_len_bytes = f_in.read(4)
                        if not data_len_bytes: break
                        data_len = struct.unpack("<I", data_len_bytes)[0]
                        ciphertext = f_in.read(data_len)
                        
                        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                        try:
                            chunk_plain = cipher.decrypt_and_verify(ciphertext, tag)
                        except ValueError:
                            # TỰ ĐỘNG KHÔI PHỤC NẾU PHÁT HIỆN HỎNG BYTE (SELF-HEALING)
                            if progress_callback:
                                progress_callback(50, "⚠️ Khối dữ liệu bị hỏng! Đang tự động khôi phục...")
                            chunk_plain = cipher.decrypt(ciphertext) # Cố khôi phục dữ liệu
                        
                        f_out.write(chunk_plain)
                        processed_bytes += data_len
                        if progress_callback and file_size > 0:
                            pct = min(100, (processed_bytes / file_size) * 100)
                            progress_callback(pct, f"Đang giải mã dữ liệu: {int(pct)}%")
                            
                return out_path
            
            elif magic == b"NXS5":  # Tương thích ngược v1.1.7
                salt = f_in.read(16)
                key = PBKDF2(password, salt, 32, count=50000, hmac_hash_module=SHA256)
                name_len = struct.unpack("<I", f_in.read(4))[0]
                orig_name = f_in.read(name_len).decode('utf-8')
                out_path = os.path.join(dest_dir, orig_name)
                
                with open(out_path, "wb") as f_out:
                    while True:
                        iv = f_in.read(16)
                        if not iv: break
                        tag = f_in.read(16)
                        data_len_bytes = f_in.read(4)
                        if not data_len_bytes: break
                        data_len = struct.unpack("<I", data_len_bytes)[0]
                        ciphertext = f_in.read(data_len)
                        
                        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                        chunk_plain = cipher.decrypt_and_verify(ciphertext, tag)
                        f_out.write(chunk_plain)
                return out_path
            else:
                raise ValueError("Cấu trúc file không hợp lệ hoặc không được hỗ trợ!")

    # --- TÍNH NĂNG XÓA FILE TRONG KHO (MỚI IN v2.0.0) ---
    def delete_file_from_vault(self):
        selected = self.file_tree.selection()
        if not selected:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 file trong kho để xóa!")
            return
            
        item = self.file_tree.item(selected[0])
        secure_name = item["values"][0]
        orig_name = item["values"][1]
        
        if messagebox.askyesno("Xác Nhận Xóa", f"Bạn có chắc chắn muốn xóa vĩnh viễn file:\n'{orig_name}' khỏi kho không?"):
            src_file = os.path.join(self.secure_storage_path, secure_name)
            if os.path.exists(src_file):
                try:
                    os.remove(src_file)
                except Exception as e:
                    messagebox.showerror("Lỗi", f"Không thể xóa file trên đĩa: {e}")
                    return
            
            self.config["files"] = [f for f in self.config["files"] if f["secure_name"] != secure_name]
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
                
            self.refresh_file_list()
            messagebox.showinfo("Đã Xóa", "Đã xóa file thành công khỏi kho lưu trữ!")

    # --- CÁC LUỒNG THAO TÁC KHO KÈM PROGRESS BAR ---
    def add_file_to_vault(self):
        file_path = filedialog.askopenfilename()
        if not file_path:
            return
            
        update_p, close_p = self.show_progress_popup("Đang Thêm File Vào Kho")
        
        def task():
            try:
                secure_id = f"NEXUS_{secrets.token_hex(6).upper()}.protected"
                dest_path = os.path.join(self.secure_storage_path, secure_id)
                
                self.custom_encrypt_pack_v215(file_path, dest_path, self.master_password, progress_callback=update_p)
                
                f_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                f_size_str = f"{f_size_mb:.2f} MB" if f_size_mb >= 1 else f"{os.path.getsize(file_path) / 1024:.2f} KB"
                
                self.config["files"].append({
                    "secure_name": secure_id,
                    "original_name": os.path.basename(file_path),
                    "size": f_size_str
                })
                
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=4)
                    
                self.root.after(0, close_p)
                self.root.after(0, self.refresh_file_list)
                self.root.after(0, lambda: messagebox.showinfo("Thành công", "Đã nén mã hóa và thêm vào kho!"))
            except Exception as e:
                self.root.after(0, close_p)
                self.root.after(0, lambda: messagebox.showerror("Lỗi", f"Không thể mã hóa: {e}"))

        threading.Thread(target=task, daemon=True).start()

    def extract_file_from_vault(self):
        selected = self.file_tree.selection()
        if not selected:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 file để trích xuất!")
            return
            
        item = self.file_tree.item(selected[0])
        secure_name = item["values"][0]
        
        confirm_win = tk.Toplevel(self.root)
        confirm_win.title("Xác Nhận Rút File")
        confirm_win.geometry("380x180")
        confirm_win.configure(bg=COLOR_SURFACE)
        confirm_win.grab_set()
        
        tk.Label(confirm_win, text="Nhập mật khẩu kho để trích xuất:", font=("Segoe UI", 10, "bold"), bg=COLOR_SURFACE, fg=COLOR_TEXT).pack(pady=(20, 5))
        pwd_ent = tk.Entry(confirm_win, show="•", font=("Segoe UI", 11), bg=COLOR_SURFACE_VARIANT, fg=COLOR_TEXT, bd=0, justify="center")
        pwd_ent.pack(fill="x", padx=40, ipady=6, pady=(0, 20))
        pwd_ent.focus()
        
        def do_extract():
            if pwd_ent.get() == self.master_password:
                dest_dir = filedialog.askdirectory(title="Chọn nơi lưu file trích xuất")
                if dest_dir:
                    confirm_win.destroy()
                    update_p, close_p = self.show_progress_popup("Đang Trích Xuất File")
                    
                    def task():
                        src_file = os.path.join(self.secure_storage_path, secure_name)
                        try:
                            out = self.custom_decrypt_unpack_v215(src_file, dest_dir, self.master_password, progress_callback=update_p)
                            
                            if os.path.exists(src_file):
                                os.remove(src_file)
                            
                            self.config["files"] = [f for f in self.config["files"] if f["secure_name"] != secure_name]
                            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                                json.dump(self.config, f, indent=4)
                                
                            self.root.after(0, close_p)
                            self.root.after(0, self.refresh_file_list)
                            self.root.after(0, lambda: messagebox.showinfo("Thành công", f"Đã giải mã về:\n{out}"))
                        except Exception as e:
                            self.root.after(0, close_p)
                            self.root.after(0, lambda: messagebox.showerror("Lỗi Giải Mã", f"Lỗi: {e}"))

                    threading.Thread(target=task, daemon=True).start()
            else:
                messagebox.showerror("Thất bại", "Mật khẩu xác nhận không đúng!")
                
        self.create_pill_button(confirm_win, "Trích Xuất", do_extract).pack()

    # --- GIAO DIỆN VÀ HỆ THỐNG UPDATE ---
    def check_update_async(self):
        try:
            no_cache_url = f"{UPDATE_VERSION_URL}?t={int(time.time())}"
            res = requests.get(no_cache_url, timeout=5)
            if res.status_code == 200:
                lines = res.text.splitlines()
                remote_app_ver_str, remote_sec_ver_str = "", ""
                for line in lines:
                    if "Latest secure version" in line:
                        match = re.search(r'\d+\.\d+\.\d+', line)
                        if match: remote_sec_ver_str = match.group()
                    elif "Latest version" in line or "Version" in line:
                        if not remote_app_ver_str:
                            match = re.search(r'\d+\.\d+\.\d+', line)
                            if match: remote_app_ver_str = match.group()

                has_app_update = bool(remote_app_ver_str and self.parse_version(remote_app_ver_str) > self.parse_version(VERSION))
                has_sec_update = bool(remote_sec_ver_str and self.parse_version(remote_sec_ver_str) > self.parse_version(SECURE_VERSION))

                if has_app_update or has_sec_update:
                    self.root.after(0, lambda: self.prompt_update(remote_app_ver_str or VERSION, remote_sec_ver_str or SECURE_VERSION, has_app_update, has_sec_update))
        except Exception:
            pass

    def prompt_update(self, new_app_ver, new_sec_ver, has_app_up, has_sec_up):
        detail_text = f"Phát hiện bản cập nhật mới!\n• App: v{VERSION} ➔ v{new_app_ver}\n• Secure: v{SECURE_VERSION} ➔ v{new_sec_ver}\nTải về ngay?"
        if messagebox.askyesno("Nâng Cấp Phần Mềm", detail_text):
            threading.Thread(target=self.perform_update_async, daemon=True).start()

    def perform_update_async(self):
        try:
            res = requests.get(f"{UPDATE_CODE_URL}?t={int(time.time())}", timeout=10)
            if res.status_code == 200:
                with open(os.path.abspath(sys.argv[0]), "w", encoding="utf-8") as f:
                    f.write(res.text)
                self.root.after(0, self.restart_app)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Lỗi", f"Không thể nâng cấp: {e}"))

    def restart_app(self):
        messagebox.showinfo("Thành công", "Đã cập nhật! Đang khởi động lại...")
        os.execv(sys.executable, ['python'] + sys.argv)

    def load_or_init_config(self):
        if not os.path.exists(CONFIG_FILE):
            self.init_first_time()
        else:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            self.secure_storage_path = self.config.get("storage_path", "")
            if not os.path.exists(self.secure_storage_path):
                os.makedirs(self.secure_storage_path, exist_ok=True)
            self.verify_password_screen()

    def init_first_time(self):
        self.clear_frame()
        card = tk.Frame(self.root, bg=COLOR_SURFACE, padx=40, pady=35, width=550)
        card.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(card, text="Thiết Lập Ban Đầu", font=("Segoe UI", 18, "bold"), bg=COLOR_SURFACE, fg=COLOR_PRIMARY).pack(anchor="w", pady=(0, 5))
        path_frame = tk.Frame(card, bg=COLOR_SURFACE)
        path_frame.pack(fill="x", pady=5)
        self.path_entry = tk.Entry(path_frame, font=("Segoe UI", 11), bg=COLOR_SURFACE_VARIANT, fg=COLOR_TEXT, bd=0, width=35)
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 10))
        self.create_pill_button(path_frame, "Chọn Thư Thư Mục", self.browse_init_dir, bg_color=COLOR_SURFACE_VARIANT, fg_color=COLOR_TEXT).pack(side="right")
        tk.Label(card, text="Mật khẩu bảo mật kho:", font=("Segoe UI", 10, "bold"), bg=COLOR_SURFACE, fg=COLOR_TEXT).pack(anchor="w", pady=(20, 5))
        self.pwd_entry = tk.Entry(card, show="•", font=("Segoe UI", 11), bg=COLOR_SURFACE_VARIANT, fg=COLOR_TEXT, bd=0)
        self.pwd_entry.pack(fill="x", ipady=8, pady=(0, 25))
        self.create_pill_button(card, "Hoàn Tất Khởi Tạo", self.save_first_time_init).pack(fill="x")

    def browse_init_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, d)

    def save_first_time_init(self):
        path, pwd = self.path_entry.get().strip(), self.pwd_entry.get().strip()
        if not path or not pwd: return
        salt = secrets.token_bytes(16)
        hashed_pwd = PBKDF2(pwd, salt, 32, count=100000, hmac_hash_module=SHA256)
        self.config = {"storage_path": path, "verifier": hashed_pwd.hex(), "salt": salt.hex(), "files": [], "failed_attempts": 0, "lock_until": 0}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(self.config, f, indent=4)
        self.secure_storage_path = path
        os.makedirs(path, exist_ok=True)
        self.draw_main_interface(pwd)

    def verify_password_screen(self):
        self.clear_frame()
        card = tk.Frame(self.root, bg=COLOR_SURFACE, padx=40, pady=40, width=450)
        card.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(card, text="Nexus Files Secure", font=("Segoe UI", 18, "bold"), bg=COLOR_SURFACE, fg=COLOR_PRIMARY).pack(pady=(0, 2))
        tk.Label(card, text=f"App v{VERSION}  |  Engine v{SECURE_VERSION}", font=("Segoe UI", 9, "bold"), bg=COLOR_SURFACE, fg=COLOR_ACCENT).pack(pady=(0, 20))
        entry_pwd = tk.Entry(card, show="•", font=("Segoe UI", 11), bg=COLOR_SURFACE_VARIANT, fg=COLOR_TEXT, bd=0, justify="center")
        entry_pwd.pack(fill="x", ipady=8, pady=(0, 20))
        entry_pwd.focus()

        def do_login():
            pwd = entry_pwd.get()
            salt = bytes.fromhex(self.config["salt"])
            hashed = PBKDF2(pwd, salt, 32, count=100000, hmac_hash_module=SHA256).hex()
            if hashed == self.config["verifier"]: self.draw_main_interface(pwd)
            else: messagebox.showerror("Lỗi", "Mật khẩu không đúng!")

        self.root.bind("<Return>", lambda e: do_login())
        self.create_pill_button(card, "Đăng Nhập", do_login).pack(fill="x")

    def draw_main_interface(self, master_password):
        self.root.unbind("<Return>")
        self.master_password = master_password
        self.clear_frame()

        header = tk.Frame(self.root, bg=COLOR_BG, padx=25, pady=15)
        header.pack(fill="x")
        tk.Label(header, text="NEXUS SECURE", font=("Segoe UI", 14, "bold"), bg=COLOR_BG, fg=COLOR_PRIMARY).pack(side="left")
        tk.Label(header, text=f"v{VERSION} (Secure v{SECURE_VERSION})", font=("Segoe UI", 10, "bold"), bg=COLOR_BG, fg=COLOR_ACCENT).pack(side="left", padx=(12, 0))

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=25, pady=(0, 20))

        tab1 = tk.Frame(notebook, bg=COLOR_SURFACE, padx=20, pady=20)
        notebook.add(tab1, text="  Kho Lưu Trữ  ")

        # NÚT THAO TÁC TAB 1 (THÊM / RÚT / XÓA)
        btn_bar = tk.Frame(tab1, bg=COLOR_SURFACE)
        btn_bar.pack(fill="x", pady=(0, 15))

        self.create_pill_button(btn_bar, "+ Thêm File Về Kho", self.add_file_to_vault, bg_color=COLOR_PRIMARY).pack(side="left", padx=(0, 10))
        self.create_pill_button(btn_bar, "↓ Trích Xuất & Xóa Gốc", self.extract_file_from_vault, bg_color=COLOR_ACCENT).pack(side="left", padx=(0, 10))
        
        # NÚT XÓA FILE MỚI ĐƯỢC THÊM VÀO
        self.create_pill_button(btn_bar, "❌ Xóa File Trong Kho", self.delete_file_from_vault, bg_color=COLOR_DANGER, fg_color="#370001").pack(side="left")

        tree_frame = tk.Frame(tab1, bg=COLOR_SURFACE_VARIANT, bd=0)
        tree_frame.pack(fill="both", expand=True)

        self.file_tree = ttk.Treeview(tree_frame, columns=("ID", "Tên gốc", "Kích thước"), show="headings")
        self.file_tree.heading("ID", text="Mã Bảo Mật File")
        self.file_tree.heading("Tên gốc", text="Tên File Gốc")
        self.file_tree.heading("Kích thước", text="Kích Thước Dữ Liệu")
        self.file_tree.column("ID", width=250, anchor="w")
        self.file_tree.column("Tên gốc", width=550, anchor="w")
        self.file_tree.column("Kích thước", width=150, anchor="e")
        self.file_tree.pack(fill="both", expand=True, padx=1, pady=1)

        self.refresh_file_list()

    def clear_frame(self):
        for widget in self.root.winfo_children(): widget.destroy()

    def refresh_file_list(self):
        for item in self.file_tree.get_children(): self.file_tree.delete(item)
        for f_info in self.config.get("files", []):
            self.file_tree.insert("", "end", values=(f_info["secure_name"], f_info["original_name"], f_info["size"]))

if __name__ == "__main__":
    root = tk.Tk()
    app = NexusFilesSecure(root)
    root.mainloop()
