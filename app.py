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
VERSION = "1.1.5"
SECURE_VERSION = "2.0.0"

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
        self.root.title(f"Nexus Files Secure - App v{VERSION} | Secure v{SECURE_VERSION}")
        self.root.geometry("660x560")
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)
        
        self.config = {}
        self.secure_storage_path = ""
        self.master_password = ""
        self.selected_ext_file = ""

        self.setup_android_theme()
        
        # Kiểm tra cập nhật chạy ngầm
        threading.Thread(target=self.check_update_async, daemon=True).start()
        
        self.load_or_init_config()

    # --- TÍNH TOÁN RAM TRỐNG (TỐI ĐA 80% RAM TRỐNG) ---
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
            
        chunk_size = min(max_allowed, 16 * 1024 * 1024)
        return max(chunk_size, 1 * 1024 * 1024)

    # --- THIẾT LẬP THEME ANDROID 16 ---
    def setup_android_theme(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=COLOR_SURFACE, foreground=COLOR_TEXT_MUTED, 
                             padding=[16, 8], font=("Segoe UI", 10, "bold"), borderwidth=0)
        self.style.map("TNotebook.Tab", 
                       background=[("selected", COLOR_SURFACE_VARIANT)],
                       foreground=[("selected", COLOR_PRIMARY)])

        self.style.configure("Treeview", background=COLOR_SURFACE, foreground=COLOR_TEXT, 
                             fieldbackground=COLOR_SURFACE, rowheight=32, font=("Segoe UI", 10), borderwidth=0)
        self.style.configure("Treeview.Heading", background=COLOR_SURFACE_VARIANT, foreground=COLOR_TEXT, 
                             font=("Segoe UI", 9, "bold"), borderwidth=0)
        self.style.map("Treeview", background=[("selected", COLOR_SURFACE_VARIANT)], foreground=[("selected", COLOR_PRIMARY)])

    def create_pill_button(self, parent, text, command, bg_color=COLOR_PRIMARY, fg_color=COLOR_ON_PRIMARY, width=None):
        return tk.Button(parent, text=text, command=command, bg=bg_color, fg=fg_color,
                         activebackground=COLOR_ACCENT, activeforeground=COLOR_ON_PRIMARY,
                         font=("Segoe UI", 10, "bold"), relief="flat", bd=0, padx=14, pady=6,
                         cursor="hand2", width=width)

    def parse_version(self, version_str):
        try:
            return tuple(map(int, version_str.strip().split('.')))
        except ValueError:
            return (0, 0, 0)

    # --- HỆ THỐNG CHECK VÀ PHÂN LOẠI BẢN CẬP NHẬT ---
    def check_update_async(self):
        try:
            res = requests.get(UPDATE_VERSION_URL, timeout=4)
            if res.status_code == 200:
                lines = res.text.splitlines()
                remote_app_ver_str = ""
                remote_sec_ver_str = ""
                
                for line in lines:
                    # Đọc phiên bản bảo mật
                    if "Latest secure version" in line:
                        match = re.search(r'\d+\.\d+\.\d+', line)
                        if match:
                            remote_sec_ver_str = match.group()
                    # Đọc phiên bản ứng dụng
                    elif "Latest version" in line or "Version" in line:
                        if not remote_app_ver_str:
                            match = re.search(r'\d+\.\d+\.\d+', line)
                            if match:
                                remote_app_ver_str = match.group()

                has_app_update = bool(remote_app_ver_str and self.parse_version(remote_app_ver_str) > self.parse_version(VERSION))
                has_sec_update = bool(remote_sec_ver_str and self.parse_version(remote_sec_ver_str) > self.parse_version(SECURE_VERSION))

                if has_app_update or has_sec_update:
                    self.root.after(0, lambda: self.prompt_update(
                        remote_app_ver_str or VERSION,
                        remote_sec_ver_str or SECURE_VERSION,
                        has_app_update,
                        has_sec_update
                    ))
        except Exception:
            pass

    def prompt_update(self, new_app_ver, new_sec_ver, has_app_up, has_sec_up):
        # Xác định loại cập nhật dựa vào trạng thái phiên bản
        if has_app_up and has_sec_up:
            update_type_msg = "📌 Loại cập nhật: Cập nhật toàn diện (Bao gồm tính năng mới và nâng cấp bảo mật quan trọng)."
        elif has_app_up and not has_sec_up:
            update_type_msg = "📌 Loại cập nhật: Cập nhật tính năng, không ảnh hưởng đến bảo mật."
        elif has_sec_up and not has_app_up:
            update_type_msg = "📌 Loại cập nhật: Cập nhật liên quan đến bảo mật, không làm thay đổi tính năng."
        else:
            return

        detail_text = (
            f"Phát hiện bản cập nhật mới trên GitHub!\n\n"
            f"• Phiên bản Ứng dụng: v{VERSION} ➔ v{new_app_ver}\n"
            f"• Phiên bản Bảo mật:   v{SECURE_VERSION} ➔ v{new_sec_ver}\n\n"
            f"{update_type_msg}\n\n"
            f"Bạn có muốn tiến hành nâng cấp tự động ngay không?"
        )

        self.root.clipboard_clear()
        self.root.clipboard_append(detail_text)
        self.root.update()

        if messagebox.askyesno("Phát Hiện Bản Cập Nhật Mới", detail_text):
            threading.Thread(target=self.perform_update_async, daemon=True).start()

    def perform_update_async(self):
        try:
            res = requests.get(UPDATE_CODE_URL, timeout=10)
            if res.status_code == 200:
                current_script = os.path.abspath(sys.argv[0])
                with open(current_script, "w", encoding="utf-8") as f:
                    f.write(res.text)
                self.root.after(0, self.restart_app)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Lỗi Cập Nhật", f"Không thể tải mã nguồn mới: {e}"))

    def restart_app(self):
        messagebox.showinfo("Thành công", "Đã cập nhật hệ thống thành công! Ứng dụng sẽ khởi động lại.")
        os.execv(sys.executable, ['python'] + sys.argv)

    # --- XEM NỘI DUNG README GỐC ---
    def fetch_and_show_software_info(self):
        def task():
            try:
                res = requests.get(UPDATE_VERSION_URL, timeout=5)
                if res.status_code == 200:
                    raw_text = res.text
                    self.root.clipboard_clear()
                    self.root.clipboard_append(raw_text)
                    self.root.update()
                    self.root.after(0, lambda: self.display_readme_window(raw_text))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Lỗi", "Không thể tải file README.md"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi", f"Lỗi kết nối: {e}"))

        threading.Thread(target=task, daemon=True).start()

    def display_readme_window(self, content):
        info_win = tk.Toplevel(self.root)
        info_win.title("Thông Tin Phiên Bản & Bảo Mật - README")
        info_win.geometry("620x500")
        info_win.configure(bg=COLOR_BG)

        hdr = tk.Frame(info_win, bg=COLOR_BG, padx=15, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Chi Tiết README (Đã copy vào Clipboard)", font=("Segoe UI", 11, "bold"), bg=COLOR_BG, fg=COLOR_PRIMARY).pack(side="left")

        txt_frame = tk.Frame(info_win, bg=COLOR_SURFACE, padx=10, pady=10)
        txt_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        txt_box = tk.Text(txt_frame, wrap="word", bg=COLOR_SURFACE, fg=COLOR_TEXT, 
                          font=("Segoe UI", 11), bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(txt_frame, command=txt_box.yview)
        txt_box.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        txt_box.pack(side="left", fill="both", expand=True)

        txt_box.insert("1.0", content)
        txt_box.config(state="disabled")

    # --- QUẢN LÝ CẤU HÌNH ---
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
        card = tk.Frame(self.root, bg=COLOR_SURFACE, padx=30, pady=25)
        card.pack(expand=True, padx=40, pady=40, fill="both")
        
        tk.Label(card, text="Thiết Lập Ban Đầu", font=("Segoe UI", 16, "bold"), bg=COLOR_SURFACE, fg=COLOR_PRIMARY).pack(anchor="w", pady=(0, 5))
        tk.Label(card, text="Chọn thư mục kho lưu trữ và tạo mật khẩu chính.", font=("Segoe UI", 10), bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED).pack(anchor="w", pady=(0, 20))
        
        path_frame = tk.Frame(card, bg=COLOR_SURFACE)
        path_frame.pack(fill="x", pady=5)
        
        self.path_entry = tk.Entry(path_frame, font=("Segoe UI", 10), bg=COLOR_SURFACE_VARIANT, fg=COLOR_TEXT, bd=0, highlightthickness=1, highlightbackground=COLOR_TEXT_MUTED)
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        
        btn_browse = self.create_pill_button(path_frame, "Chọn Thư Mục", self.browse_init_dir, bg_color=COLOR_SURFACE_VARIANT, fg_color=COLOR_TEXT)
        btn_browse.pack(side="right")
        
        tk.Label(card, text="Mật khẩu bảo mật kho:", font=("Segoe UI", 10, "bold"), bg=COLOR_SURFACE, fg=COLOR_TEXT).pack(anchor="w", pady=(15, 5))
        self.pwd_entry = tk.Entry(card, show="•", font=("Segoe UI", 10), bg=COLOR_SURFACE_VARIANT, fg=COLOR_TEXT, bd=0, highlightthickness=1, highlightbackground=COLOR_TEXT_MUTED)
        self.pwd_entry.pack(fill="x", ipady=6, pady=(0, 20))
        
        btn_save = self.create_pill_button(card, "Hoàn Tất Khởi Tạo", self.save_first_time_init)
        btn_save.pack(fill="x")

    def browse_init_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, d)

    def save_first_time_init(self):
        path = self.path_entry.get().strip()
        pwd = self.pwd_entry.get().strip()
        if not path or not pwd:
            messagebox.showwarning("Cảnh báo", "Vui lòng điền đầy đủ thông tin!")
            return
        
        salt = secrets.token_bytes(16)
        hashed_pwd = PBKDF2(pwd, salt, 32, count=100000, hmac_hash_module=SHA256)
        
        self.config = {
            "storage_path": path,
            "verifier": hashed_pwd.hex(),
            "salt": salt.hex(),
            "files": [],
            "failed_attempts": 0,
            "lock_until": 0
        }
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)
            
        self.secure_storage_path = path
        os.makedirs(path, exist_ok=True)
        self.draw_main_interface(pwd)

    # --- MÀN HÌNH ĐĂNG NHẬP ---
    def verify_password_screen(self):
        self.clear_frame()
        card = tk.Frame(self.root, bg=COLOR_SURFACE, padx=30, pady=30)
        card.pack(expand=True, padx=80, pady=60, fill="both")
        
        tk.Label(card, text="Nexus Files Secure", font=("Segoe UI", 16, "bold"), bg=COLOR_SURFACE, fg=COLOR_PRIMARY).pack(pady=(0, 2))
        
        # Màn hình đăng nhập hiển thị chi tiết 2 thông số phiên bản
        lbl_ver_sub = tk.Label(card, text=f"App v{VERSION}  |  Secure Engine v{SECURE_VERSION}", font=("Segoe UI", 9, "bold"), bg=COLOR_SURFACE, fg=COLOR_ACCENT)
        lbl_ver_sub.pack(pady=(0, 15))

        tk.Label(card, text="Nhập mật khẩu truy cập kho lưu trữ", font=("Segoe UI", 10), bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED).pack(pady=(0, 15))
        
        entry_pwd = tk.Entry(card, show="•", font=("Segoe UI", 11), bg=COLOR_SURFACE_VARIANT, fg=COLOR_TEXT, bd=0, justify="center", highlightthickness=1, highlightbackground=COLOR_TEXT_MUTED)
        entry_pwd.pack(fill="x", ipady=8, pady=(0, 20))
        entry_pwd.focus()

        def do_login():
            pwd = entry_pwd.get()
            salt = bytes.fromhex(self.config["salt"])
            expected = self.config["verifier"]
            hashed = PBKDF2(pwd, salt, 32, count=100000, hmac_hash_module=SHA256).hex()
            
            if hashed == expected:
                self.draw_main_interface(pwd)
            else:
                messagebox.showerror("Thất bại", "Mật khẩu truy cập không chính xác!")

        self.root.bind("<Return>", lambda e: do_login())
        btn_login = self.create_pill_button(card, "Đăng Nhập", do_login)
        btn_login.pack(fill="x")

    # --- GIAO DIỆN CHÍNH ---
    def draw_main_interface(self, master_password):
        self.root.unbind("<Return>")
        self.master_password = master_password
        self.clear_frame()

        header = tk.Frame(self.root, bg=COLOR_BG, padx=20, pady=10)
        header.pack(fill="x")
        
        tk.Label(header, text="NEXUS SECURE", font=("Segoe UI", 12, "bold"), bg=COLOR_BG, fg=COLOR_PRIMARY).pack(side="left")
        
        # Hiển thị rõ phiên bản App và phiên bản Bảo Mật trên Thanh Tiêu Đề Top Bar
        ver_info_text = f"v{VERSION} (Secure v{SECURE_VERSION})"
        tk.Label(header, text=ver_info_text, font=("Segoe UI", 9, "bold"), bg=COLOR_BG, fg=COLOR_ACCENT).pack(side="left", padx=(8, 0))

        btn_info = self.create_pill_button(header, "Thông Tin Phiên Bản", self.fetch_and_show_software_info, bg_color=COLOR_SURFACE_VARIANT, fg_color=COLOR_TEXT)
        btn_info.pack(side="right")

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        tab1 = tk.Frame(notebook, bg=COLOR_SURFACE, padx=15, pady=15)
        tab2 = tk.Frame(notebook, bg=COLOR_SURFACE, padx=15, pady=15)

        notebook.add(tab1, text="  Kho Lưu Trữ  ")
        notebook.add(tab2, text="  Giải Mã Ngoại Vi  ")

        # TAB 1
        btn_bar = tk.Frame(tab1, bg=COLOR_SURFACE)
        btn_bar.pack(fill="x", pady=(0, 12))

        btn_add = self.create_pill_button(btn_bar, "+ Thêm File", self.add_file_to_vault, bg_color=COLOR_PRIMARY)
        btn_add.pack(side="left", padx=(0, 10))

        btn_ext = self.create_pill_button(btn_bar, "↓ Trích Xuất & Xóa Gốc", self.extract_file_from_vault, bg_color=COLOR_ACCENT)
        btn_ext.pack(side="left")

        tree_frame = tk.Frame(tab1, bg=COLOR_SURFACE_VARIANT, bd=0)
        tree_frame.pack(fill="both", expand=True)

        self.file_tree = ttk.Treeview(tree_frame, columns=("ID", "Tên gốc", "Kích thước"), show="headings")
        self.file_tree.heading("ID", text="Mã Bảo Mật")
        self.file_tree.heading("Tên gốc", text="Tên File Gốc")
        self.file_tree.heading("Kích thước", text="Kích Thước")

        self.file_tree.column("ID", width=160, anchor="w")
        self.file_tree.column("Tên gốc", width=290, anchor="w")
        self.file_tree.column("Kích thước", width=100, anchor="e")
        self.file_tree.pack(fill="both", expand=True, padx=1, pady=1)

        self.refresh_file_list()

        # TAB 2
        card_ext = tk.Frame(tab2, bg=COLOR_SURFACE_VARIANT, padx=20, pady=20)
        card_ext.pack(fill="x", pady=10)

        tk.Label(card_ext, text="Giải Nén File Dị Biệt (.protected)", font=("Segoe UI", 11, "bold"), bg=COLOR_SURFACE_VARIANT, fg=COLOR_TEXT).pack(anchor="w", pady=(0, 5))
        
        self.lbl_ext_file = tk.Label(card_ext, text="Chưa chọn file nào", font=("Segoe UI", 10, "italic"), bg=COLOR_SURFACE_VARIANT, fg=COLOR_TEXT_MUTED)
        self.lbl_ext_file.pack(anchor="w", pady=(0, 10))

        btn_choose = self.create_pill_button(card_ext, "Chọn File Ngoại Vi", self.choose_ext_file, bg_color=COLOR_SURFACE, fg_color=COLOR_TEXT)
        btn_choose.pack(anchor="w", pady=(0, 15))

        tk.Label(card_ext, text="Mật khẩu của file:", font=("Segoe UI", 10, "bold"), bg=COLOR_SURFACE_VARIANT, fg=COLOR_TEXT).pack(anchor="w", pady=(5, 5))
        self.ext_pwd_entry = tk.Entry(card_ext, show="•", font=("Segoe UI", 10), bg=COLOR_SURFACE, fg=COLOR_TEXT, bd=0, highlightthickness=1, highlightbackground=COLOR_TEXT_MUTED)
        self.ext_pwd_entry.pack(fill="x", ipady=6, pady=(0, 15))

        btn_decrypt = self.create_pill_button(card_ext, "Tiến Hành Giải Mã & Xóa File Gốc", self.decrypt_external_file, bg_color=COLOR_DANGER, fg_color="#370001")
        btn_decrypt.pack(fill="x")

    def clear_frame(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def refresh_file_list(self):
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        for f_info in self.config.get("files", []):
            self.file_tree.insert("", "end", values=(f_info["secure_name"], f_info["original_name"], f_info["size"]))

    def choose_ext_file(self):
        f = filedialog.askopenfilename(filetypes=[("Nexus Protected", "*.protected")])
        if f:
            self.selected_ext_file = f
            self.lbl_ext_file.config(text=os.path.basename(f), fg=COLOR_PRIMARY, font=("Segoe UI", 10, "bold"))

    # --- THUẬT TOÁN MÃ HÓA LUỒNG STREAMING CHUNKING (V1.1.5) ---
    def custom_encrypt_pack(self, src_path, dest_path, password):
        salt = secrets.token_bytes(16)
        key = PBKDF2(password, salt, 32, count=50000, hmac_hash_module=SHA256)
        chunk_size = self.get_safe_chunk_size()
        
        orig_name_bytes = os.path.basename(src_path).encode('utf-8')
        
        with open(src_path, "rb") as f_in, open(dest_path, "wb") as f_out:
            # Struct Header v1.1.5 Magic Key NXS5
            f_out.write(b"NXS5")
            f_out.write(salt)
            f_out.write(struct.pack("<I", len(orig_name_bytes)))
            f_out.write(orig_name_bytes)
            
            while True:
                chunk = f_in.read(chunk_size)
                if not chunk:
                    break
                
                iv = secrets.token_bytes(16)
                cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                ciphertext, tag = cipher.encrypt_and_digest(chunk)
                
                f_out.write(iv)
                f_out.write(tag)
                f_out.write(struct.pack("<I", len(ciphertext)))
                f_out.write(ciphertext)

    # --- GIẢI MÃ TƯƠNG THÍCH NGƯỢC ---
    def custom_decrypt_unpack(self, src_path, dest_dir, password):
        with open(src_path, "rb") as f_in:
            magic = f_in.read(4)
            
            # --- CHUẨN MỚI V1.1.5 CHUNK STREAMING ---
            if magic == b"NXS5":
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
                        data_len_bytes = f_in.read(4)
                        if not data_len_bytes:
                            break
                        data_len = struct.unpack("<I", data_len_bytes)[0]
                        ciphertext = f_in.read(data_len)
                        
                        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                        chunk_plain = cipher.decrypt_and_verify(ciphertext, tag)
                        f_out.write(chunk_plain)
                return out_path
            
            # --- CHUẨN CŨ V1.1.0 SINGLE BLOCK ---
            elif magic == b"NXSD":
                salt = f_in.read(16)
                iv = f_in.read(16)
                tag = f_in.read(16)
                ciphertext = f_in.read()
                
                key = PBKDF2(password, salt, 32, count=50000, hmac_hash_module=SHA256)
                cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                decrypted_payload = cipher.decrypt_and_verify(ciphertext, tag)
                
                name_len = struct.unpack("<I", decrypted_payload[:4])[0]
                orig_name = decrypted_payload[4:4+name_len].decode('utf-8')
                file_data = decrypted_payload[4+name_len:-7]
                
                out_path = os.path.join(dest_dir, orig_name)
                with open(out_path, "wb") as f_out:
                    f_out.write(file_data)
                return out_path
            else:
                raise ValueError("Định dạng file bị lỗi hoặc không hỗ trợ!")

    # --- THAO TÁC KHO BẢO MẬT ---
    def add_file_to_vault(self):
        file_path = filedialog.askopenfilename()
        if not file_path:
            return
            
        secure_id = f"NEXUS_{secrets.token_hex(6).upper()}.protected"
        dest_path = os.path.join(self.secure_storage_path, secure_id)
        
        try:
            self.custom_encrypt_pack(file_path, dest_path, self.master_password)
            f_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            f_size_str = f"{f_size_mb:.2f} MB" if f_size_mb >= 1 else f"{os.path.getsize(file_path) / 1024:.2f} KB"
            
            self.config["files"].append({
                "secure_name": secure_id,
                "original_name": os.path.basename(file_path),
                "size": f_size_str
            })
            
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
                
            self.refresh_file_list()
            messagebox.showinfo("Thành công", "Đã nén mã hóa và thêm vào kho lưu trữ!")
        except Exception as e:
            messagebox.showerror("Lỗi Mã Hóa", f"Không thể xử lý file: {e}")

    def extract_file_from_vault(self):
        selected = self.file_tree.selection()
        if not selected:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 file để trích xuất!")
            return
            
        item = self.file_tree.item(selected[0])
        secure_name = item["values"][0]
        
        confirm_win = tk.Toplevel(self.root)
        confirm_win.title("Xác Nhận Rút File")
        confirm_win.geometry("340x160")
        confirm_win.configure(bg=COLOR_SURFACE)
        confirm_win.grab_set()
        
        tk.Label(confirm_win, text="Nhập mật khẩu kho để trích xuất:", font=("Segoe UI", 10, "bold"), bg=COLOR_SURFACE, fg=COLOR_TEXT).pack(pady=(15, 5))
        pwd_ent = tk.Entry(confirm_win, show="•", font=("Segoe UI", 10), bg=COLOR_SURFACE_VARIANT, fg=COLOR_TEXT, bd=0, justify="center")
        pwd_ent.pack(fill="x", padx=30, ipady=5, pady=(0, 15))
        pwd_ent.focus()
        
        def do_extract():
            if pwd_ent.get() == self.master_password:
                dest_dir = filedialog.askdirectory(title="Chọn nơi lưu file trích xuất")
                if dest_dir:
                    src_file = os.path.join(self.secure_storage_path, secure_name)
                    try:
                        out = self.custom_decrypt_unpack(src_file, dest_dir, self.master_password)
                        
                        if os.path.exists(src_file):
                            os.remove(src_file)
                        
                        self.config["files"] = [f for f in self.config["files"] if f["secure_name"] != secure_name]
                        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                            json.dump(self.config, f, indent=4)
                            
                        self.refresh_file_list()
                        confirm_win.destroy()
                        messagebox.showinfo("Thành công", f"Trích xuất thành công về:\n{out}\n(Đã dọn dẹp file mã hóa trong kho)")
                    except Exception as e:
                        messagebox.showerror("Lỗi Giải Mã", f"Không thể giải mã: {e}")
            else:
                messagebox.showerror("Thất bại", "Mật khẩu xác nhận không đúng!")
                
        self.create_pill_button(confirm_win, "Trích Xuất", do_extract).pack()

    def decrypt_external_file(self):
        if not self.selected_ext_file:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn file .protected ngoại vi trước!")
            return
            
        pwd = self.ext_pwd_entry.get().strip()
        if not pwd:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập mật khẩu riêng của file!")
            return

        failed_attempts = self.config.get("failed_attempts", 0)
        lock_until = self.config.get("lock_until", 0)
        current_time = time.time()
        
        if current_time < lock_until:
            remains = int(lock_until - current_time)
            if lock_until > 2000000000:
                messagebox.showerror("KHÓA VĨNH VIỄN", "Ứng dụng đã bị khóa vĩnh viễn do sai mật khẩu quá 20 lần!")
            else:
                messagebox.showerror("TẠM KHÓA BẢO MẬT", f"Vui lòng đợi {remains} giây trước khi thử lại.")
            return

        try:
            dest_dir = filedialog.askdirectory(title="Chọn thư mục lưu file giải nén")
            if not dest_dir:
                return
                
            out = self.custom_decrypt_unpack(self.selected_ext_file, dest_dir, pwd)
            
            if os.path.exists(self.selected_ext_file):
                os.remove(self.selected_ext_file)
                self.selected_ext_file = ""
                self.lbl_ext_file.config(text="Chưa chọn file nào", fg=COLOR_TEXT_MUTED, font=("Segoe UI", 10, "italic"))
                self.ext_pwd_entry.delete(0, tk.END)

            self.config["failed_attempts"] = 0
            self.config["lock_until"] = 0
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
                
            messagebox.showinfo("Thành công", f"Giải nén thành công về:\n{out}\n(File gốc .protected đã được xóa)")
            
        except Exception:
            failed_attempts += 1
            self.config["failed_attempts"] = failed_attempts
            
            if failed_attempts >= 20:
                self.config["lock_until"] = 9999999999
                penalty_msg = "Sai 20 lần! Hệ thống đã khóa vĩnh viễn."
            elif failed_attempts >= 15:
                self.config["lock_until"] = current_time + 86400
                penalty_msg = "Sai 15 lần! Hệ thống tạm khóa 1 NGÀY."
            elif failed_attempts >= 10:
                self.config["lock_until"] = current_time + 3600
                penalty_msg = "Sai 10 lần! Hệ thống tạm khóa 1 GIỜ."
            elif failed_attempts >= 5:
                self.config["lock_until"] = current_time + 300
                penalty_msg = "Sai 5 lần! Hệ thống tạm khóa 5 PHÚT."
            else:
                penalty_msg = f"Sai mật khẩu! Bạn còn {5 - (failed_attempts % 5)} lần thử."

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
                
            messagebox.showerror("Lỗi Cấu Trúc / Sai Mật Khẩu", penalty_msg)

if __name__ == "__main__":
    root = tk.Tk()
    app = NexusFilesSecure(root)
    root.mainloop()
