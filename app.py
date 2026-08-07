import os
import sys
import json
import time
import shutil
import struct
import secrets
import requests
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256

VERSION = "1.0.1"  # Định dạng phiên bản x.x.x mới
CONFIG_FILE = "data.json"
UPDATE_VERSION_URL = "https://raw.githubusercontent.com/letranthienphat/Nexus-Files-Secure/refs/heads/main/README.md"
UPDATE_CODE_URL = "https://raw.githubusercontent.com/letranthienphat/Nexus-Files-Secure/refs/heads/main/app.py"

class NexusFilesSecure:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Nexus Files Secure v{VERSION}")
        self.root.geometry("600x450")
        self.root.resizable(False, False)
        
        self.config = {}
        self.secure_storage_path = ""
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.check_update()
        self.load_or_init_config()

    # --- HÀM TÁCH CHUỖI PHIÊN BẢN ĐỂ SO SÁNH CHÍNH XÁC ---
    def parse_version(self, version_str):
        # Chuyển từ "1.0.1" thành (1, 0, 1) để so sánh toán học chính xác
        try:
            return tuple(map(int, version_str.strip().split('.')))
        except ValueError:
            return (0, 0, 0)

    # --- TÍNH NĂNG TỰ ĐỘNG CẬP NHẬT THEO X.X.X ---
    def check_update(self):
        try:
            response = requests.get(UPDATE_VERSION_URL, timeout=5)
            if response.status_code == 200:
                import re
                # Tìm chuỗi có định dạng x.x.x đầu tiên xuất hiện trong file README.md
                match = re.search(r'\d+\.\d+\.\d+', response.text)
                if match:
                    new_version_str = match.group()
                    
                    # So sánh tuple: ví dụ (1, 0, 1) > (1, 0, 0)
                    if self.parse_version(new_version_str) > self.parse_version(VERSION):
                        if messagebox.askyesno("Cập nhật", f"Phát hiện phiên bản mới (v{new_version_str}). Cập nhật ngay?"):
                            self.perform_update()
        except Exception:
            pass 

    def perform_update(self):
        try:
            response = requests.get(UPDATE_CODE_URL, timeout=10)
            if response.status_code == 200:
                current_script = os.path.abspath(sys.argv[0])
                with open(current_script, "w", encoding="utf-8") as f:
                    f.write(response.text)
                messagebox.showinfo("Thành công", "Đã cập nhật phiên bản mới! Phần mềm sẽ tự khởi động lại.")
                os.execv(sys.executable, ['python'] + sys.argv)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể tải bản cập nhật: {e}")

    # --- KHỞI TẠO CẤU HÌNH ---
    def load_or_init_config(self):
        if not os.path.exists(CONFIG_FILE):
            self.init_first_time()
        else:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            self.secure_storage_path = self.config.get("storage_path", "")
            if not os.path.exists(self.secure_storage_path):
                os.makedirs(self.secure_storage_path)
            self.verify_password_screen()

    def init_first_time(self):
        self.init_win = tk.Toplevel(self.root)
        self.init_win.title("Cấu hình lần đầu")
        self.init_win.geometry("450x250")
        self.init_win.grab_set()
        
        tk.Label(self.init_win, text="Chào mừng đến với Nexus Files Secure", font=("Arial", 12, "bold")).pack(pady=10)
        
        path_frame = tk.Frame(self.init_win)
        path_frame.pack(pady=5, fill="x", padx=20)
        self.path_entry = tk.Entry(path_frame, width=35)
        self.path_entry.pack(side="left", padx=5)
        
        def browse_dir():
            d = filedialog.askdirectory()
            if d:
                self.path_entry.delete(0, tk.END)
                self.path_entry.insert(0, d)
                
        tk.Button(path_frame, text="Chọn nơi lưu file", command=browse_dir).pack(side="left")
        
        tk.Label(self.init_win, text="Tạo mật khẩu bảo vệ kho lưu trữ:").pack(pady=5)
        self.pwd_entry = tk.Entry(self.init_win, show="*", width=45)
        self.pwd_entry.pack(pady=5)
        
        def save_init():
            path = self.path_entry.get()
            pwd = self.pwd_entry.get()
            if not path or not pwd:
                messagebox.showwarning("Cảnh báo", "Vui lòng điền đầy đủ thông tin!")
                return
            
            salt = secrets.token_bytes(16)
            hashed_pwd = PBKDF2(pwd, salt, 32, count=100000, hmac_hash_module=SHA256)
            
            self.config = {
                "storage_path": path,
                "verifier": hashed_pwd.hex(),
                "salt": salt.hex(),
                "files": []
            }
            
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
                
            self.secure_storage_path = path
            if not os.path.exists(path):
                os.makedirs(path)
                
            with open(os.path.join(path, "README_WARNING.txt"), "w", encoding="utf-8") as w:
                w.write("CANH BAO: Tat ca cac file trong day da duoc ma hoa di biet boi Nexus Files Secure.\n"
                        "Neu ban co tinh di chuyen hoac dung phan mem khac mo, file se BI LOI VA KHONG THE DOC DUOC!")
                
            self.init_win.destroy()
            self.draw_main_interface(pwd)

        tk.Button(self.init_win, text="Hoàn tất thiết lập", command=save_init, bg="#4CAF50", fg="white").pack(pady=15)

    # --- MÀN HÌNH XÁC THỰC MẬT KHẨU ---
    def verify_password_screen(self):
        self.login_win = tk.Frame(self.root)
        self.login_win.pack(pady=50)
        
        tk.Label(self.login_win, text="NHẬP MẬT KHẨU TRUY CẬP KHO", font=("Arial", 11, "bold")).pack(pady=10)
        entry_pwd = tk.Entry(self.login_win, show="*", width=30, font=("Arial", 12))
        entry_pwd.pack(pady=5)
        
        def check():
            pwd = entry_pwd.get()
            salt = bytes.fromhex(self.config["salt"])
            expected = self.config["verifier"]
            hashed = PBKDF2(pwd, salt, 32, count=100000, hmac_hash_module=SHA256).hex()
            
            if hashed == expected:
                self.login_win.pack_forget()
                self.draw_main_interface(pwd)
            else:
                messagebox.showerror("Sai mật khẩu", "Mật khẩu truy cập phần mềm không đúng!")
                
        tk.Button(self.login_win, text="Đăng nhập", command=check, width=15, bg="#2196F3", fg="white").pack(pady=10)

    # --- GIAO DIỆN CHÍNH THỨC ---
    def draw_main_interface(self, master_password):
        self.master_password = master_password
        
        main_frame = ttk.Notebook(self.root)
        main_frame.pack(fill="both", expand=True)
        
        tab1 = ttk.Frame(main_frame)
        tab2 = ttk.Frame(main_frame)
        
        main_frame.add(tab1, text="Kho Lưu Trữ Bảo Mật")
        main_frame.add(tab2, text="Giải Mã & Giải Nén File Ngoại Vi")

        # --- TAB 1 ---
        btn_frame = tk.Frame(tab1)
        btn_frame.pack(fill="x", pady=10, padx=10)
        
        tk.Button(btn_frame, text="+ Thêm File Vào Kho", command=self.add_file_to_vault, bg="#4CAF50", fg="white").pack(side="left", padx=5)
        tk.Button(btn_frame, text="↓ Trích Xuất File Chọn", command=self.extract_file_from_vault, bg="#FF9800", fg="white").pack(side="left", padx=5)
        
        self.file_tree = ttk.Treeview(tab1, columns=("ID", "Tên gốc", "Kích thước"), show="headings")
        self.file_tree.heading("ID", text="Mã bảo mật")
        self.file_tree.heading("Tên gốc", text="Tên File Gốc")
        self.file_tree.heading("Kích thước", text="Kích thước")
        self.file_tree.column("ID", width=150)
        self.file_tree.column("Tên gốc", width=300)
        self.file_tree.column("Kích thước", width=100)
        self.file_tree.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.refresh_file_list()

        # --- TAB 2 ---
        tk.Label(tab2, text="Giải mã cấu trúc dị biệt (.protected)", font=("Arial", 11, "bold")).pack(pady=10)
        
        self.selected_ext_file = ""
        self.lbl_ext_file = tk.Label(tab2, text="Chưa chọn file nào", fg="gray")
        self.lbl_ext_file.pack(pady=5)
        
        def choose_ext_file():
            f = filedialog.askopenfilename(filetypes=[("Nexus Protected", "*.protected")])
            if f:
                self.selected_ext_file = f
                self.lbl_ext_file.config(text=os.path.basename(f), fg="black")
                
        tk.Button(tab2, text="Chọn file .protected bên ngoài", command=choose_ext_file).pack(pady=5)
        
        tk.Label(tab2, text="Nhập mật khẩu riêng của file này:").pack(pady=5)
        self.ext_pwd_entry = tk.Entry(tab2, show="*", width=30)
        self.ext_pwd_entry.pack(pady=5)
        
        tk.Button(tab2, text="Tiến hành Giải Mã & Giải Nén", command=self.decrypt_external_file, bg="#E91E63", fg="white").pack(pady=15)

    def refresh_file_list(self):
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        for f_info in self.config.get("files", []):
            self.file_tree.insert("", "end", values=(f_info["secure_name"], f_info["original_name"], f_info["size"]))

    # --- MÃ HÓA NÉN DỊ BIỆT ---
    def custom_encrypt_pack(self, src_path, dest_path, password):
        salt = secrets.token_bytes(16)
        key = PBKDF2(password, salt, 32, count=50000, hmac_hash_module=SHA256)
        
        orig_name = os.path.basename(src_path).encode('utf-8')
        with open(src_path, "rb") as f:
            file_data = f.read()
            
        header_struct = struct.pack("<I", len(orig_name))
        payload = header_struct + orig_name + file_data + secrets.token_bytes(7)
        
        iv = secrets.token_bytes(16)
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        ciphertext, tag = cipher.encrypt_and_digest(payload)
        
        with open(dest_path, "wb") as out:
            out.write(b"NXSD")
            out.write(salt)
            out.write(iv)
            out.write(tag)
            out.write(ciphertext)

    # --- GIẢI MÃ NÉN DỊ BIỆT ---
    def custom_decrypt_unpack(self, src_path, dest_dir, password):
        with open(src_path, "rb") as f:
            magic = f.read(4)
            if magic != b"NXSD":
                raise ValueError("Cấu trúc file lỗi hoặc bị giả mạo bên ngoài phần mềm!")
                
            salt = f.read(16)
            iv = f.read(16)
            tag = f.read(16)
            ciphertext = f.read()
            
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

    def add_file_to_vault(self):
        file_path = filedialog.askopenfilename()
        if not file_path:
            return
            
        secure_id = f"NEXUS_{secrets.token_hex(6).upper()}.protected"
        dest_path = os.path.join(self.secure_storage_path, secure_id)
        
        try:
            self.custom_encrypt_pack(file_path, dest_path, self.master_password)
            
            f_size = f"{os.path.getsize(file_path) / 1024:.2f} KB"
            self.config["files"].append({
                "secure_name": secure_id,
                "original_name": os.path.basename(file_path),
                "size": f_size
            })
            
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
                
            self.refresh_file_list()
            messagebox.showinfo("Thành công", "Đã nén mã hóa dị biệt và đưa vào kho thành công!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể xử lý file: {e}")

    def extract_file_from_vault(self):
        selected = self.file_tree.selection()
        if not selected:
            messagebox.showwarning("Cảnh báo", "Hãy chọn một file trong danh sách để trích xuất!")
            return
            
        item = self.file_tree.item(selected[0])
        secure_name = item["values"][0]
        
        confirm_win = tk.Toplevel(self.root)
        confirm_win.title("Xác thực")
        confirm_win.geometry("300x120")
        confirm_win.grab_set()
        
        tk.Label(confirm_win, text="Nhập mật khẩu kho để rút file:").pack(pady=5)
        pwd_ent = tk.Entry(confirm_win, show="*", width=25)
        pwd_ent.pack(pady=5)
        
        def do_extract():
            if pwd_ent.get() == self.master_password:
                dest_dir = filedialog.askdirectory(title="Chọn nơi lưu file trích xuất ra")
                if dest_dir:
                    src_file = os.path.join(self.secure_storage_path, secure_name)
                    try:
                        out = self.custom_decrypt_unpack(src_file, dest_dir, self.master_password)
                        messagebox.showinfo("Thành công", f"Đã giải mã và trích xuất về: {out}")
                        confirm_win.destroy()
                    except Exception as e:
                        messagebox.showerror("Lỗi", f"Lỗi cấu trúc giải mã: {e}")
            else:
                messagebox.showerror("Thất bại", "Mật khẩu không trùng khớp!")
                
        tk.Button(confirm_win, text="Xác nhận", command=do_extract, bg="#4CAF50", fg="white").pack(pady=5)

    # --- KHÓA TĂNG TIẾN ---
    def decrypt_external_file(self):
        if not self.selected_ext_file:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn file .protected trước!")
            return
            
        pwd = self.ext_pwd_entry.get()
        if not pwd:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập mật khẩu riêng của file!")
            return

        failed_attempts = self.config.get("failed_attempts", 0)
        lock_until = self.config.get("lock_until", 0)
        
        current_time = time.time()
        if current_time < lock_until:
            remains = int(lock_until - current_time)
            if lock_until > 2000000000:
                messagebox.showerror("BỊ KHÓA VĨNH VIỄN", "File này đã bị bảo mật khóa vĩnh viễn!")
            else:
                messagebox.showerror("Đang bị khóa", f"Vui lòng quay lại sau: {remains} giây.")
            return

        try:
            dest_dir = filedialog.askdirectory(title="Chọn nơi lưu file giải nén")
            if not dest_dir:
                return
                
            self.custom_decrypt_unpack(self.selected_ext_file, dest_dir, pwd)
            
            self.config["failed_attempts"] = 0
            self.config["lock_until"] = 0
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
                
            messagebox.showinfo("Thành công", "Giải nén cấu trúc thành công.")
            
        except Exception:
            failed_attempts += 1
            self.config["failed_attempts"] = failed_attempts
            
            if failed_attempts >= 20:
                self.config["lock_until"] = 9999999999
                penalty_msg = "Sai 20 lần! File đã bị KHÓA VĨNH VIỄN."
            elif failed_attempts >= 15:
                self.config["lock_until"] = current_time + 86400
                penalty_msg = "Sai 15 lần! Khóa phần mềm trong 1 NGÀY."
            elif failed_attempts >= 10:
                self.config["lock_until"] = current_time + 3600
                penalty_msg = "Sai 10 lần! Khóa phần mềm trong 1 GIỜ."
            elif failed_attempts >= 5:
                self.config["lock_until"] = current_time + 300
                penalty_msg = "Sai 5 lần! Khóa phần mềm trong 5 PHÚT."
            else:
                penalty_msg = f"Sai mật khẩu! Còn {5 - (failed_attempts % 5)} lần thử."

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
                
            messagebox.showerror("Lỗi bảo mật", penalty_msg)

if __name__ == "__main__":
    root = tk.Tk()
    app = NexusFilesSecure(root)
    root.mainloop()
