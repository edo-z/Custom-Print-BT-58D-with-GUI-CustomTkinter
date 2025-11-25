import time
import threading
import subprocess
import json
import os
from datetime import datetime
import customtkinter as ctk
from escpos.printer import Usb

# -------------------------------
# CONFIG FILE
# -------------------------------
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "printer_config.json")

DEFAULT_CONFIG = {
    "vendor_id": "0x0fe6",
    "product_id": "0x811e",
    "interface": 0,
    "auto_max_count": 10,
    "auto_interval": 1.0
}

def load_config():
    """Load configuration from file or return defaults"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                for key in DEFAULT_CONFIG:
                    if key not in config:
                        config[key] = DEFAULT_CONFIG[key]
                return config
    except Exception:
        pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception:
        return False

# Load config at startup
CONFIG = load_config()

# -------------------------------
# Golden Ratio Spacing System (Fibonacci)
# -------------------------------
SPACE = {
    "xs": 3,
    "sm": 5,
    "md": 8,
    "lg": 13,
    "xl": 21,
    "xxl": 34,
    "xxxl": 55,
}

PHI = 1.618

# -------------------------------
# Color Theme - Professional Dark
# -------------------------------
COLORS = {
    "bg_dark": "#0f0f1a",
    "bg_card": "#1a1a2e",
    "bg_sidebar": "#12121f",
    "accent": "#e94560",
    "accent_hover": "#ff6b6b",
    "success": "#00d9a0",
    "success_hover": "#00f5b4",
    "warning": "#ffc857",
    "text_primary": "#ffffff",
    "text_secondary": "#8892b0",
    "border": "#2d2d44",
}

# -------------------------------
# Helper: thread-safe popup
# -------------------------------
def _make_popup(master, title, message, popup_type="info"):
    win = ctk.CTkToplevel(master)
    win.title(title)
    win.geometry("377x200")
    win.configure(fg_color=COLORS["bg_card"])
    win.wait_visibility()
    win.grab_set()
    
    indicator_colors = {"success": COLORS["success"], "error": COLORS["accent"], "info": COLORS["warning"]}
    
    indicator = ctk.CTkFrame(
        win, 
        fg_color=indicator_colors.get(popup_type, COLORS["text_secondary"]),
        height=4,
        corner_radius=0
    )
    indicator.pack(fill="x")
    
    title_lbl = ctk.CTkLabel(
        win, 
        text=title.upper(),
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=indicator_colors.get(popup_type, COLORS["text_secondary"])
    )
    title_lbl.pack(pady=(SPACE["xl"], SPACE["md"]))
    
    lbl = ctk.CTkLabel(
        win, 
        text=message, 
        wraplength=int(377 - SPACE["xxl"] * 2), 
        justify="center",
        font=ctk.CTkFont(size=13),
        text_color=COLORS["text_primary"]
    )
    lbl.pack(pady=(0, SPACE["xl"]), padx=SPACE["xl"])
    
    btn = ctk.CTkButton(
        win, 
        text="OK", 
        command=win.destroy,
        fg_color=COLORS["border"],
        hover_color=COLORS["bg_sidebar"],
        font=ctk.CTkFont(size=13, weight="bold"),
        height=SPACE["xxl"],
        width=100,
        corner_radius=SPACE["sm"]
    )
    btn.pack(pady=(0, SPACE["xl"]))

# -------------------------------
# Main App
# -------------------------------
class PrinterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        
        self.title("Printer Dashboard")
        self.geometry("890x550")
        self.configure(fg_color=COLORS["bg_dark"])
        self.resizable(False, False)

        # Load config
        self.config = CONFIG.copy()
        
        # State
        self.counter = 0
        self.printer = None
        self.auto_thread = None
        self.auto_running = False
        self._stopped_by_user = False
        self.print_lock = threading.Lock()
        self.print_scheduled = False
        self._ui_lock = threading.Lock()
        self.current_mode = "Manual"
        self.device_connected = False
        
        # Auto mode settings from config
        self.auto_max_count = self.config.get("auto_max_count", 10)
        self.auto_interval = self.config.get("auto_interval", 1.0)

        self._build_ui()
        
        # Start USB monitoring
        self._start_usb_monitor()

    def _get_vendor_id(self):
        """Get vendor ID as integer"""
        try:
            vid = self.config.get("vendor_id", "0x0fe6")
            return int(vid, 16) if isinstance(vid, str) else vid
        except:
            return 0x0fe6

    def _get_product_id(self):
        """Get product ID as integer"""
        try:
            pid = self.config.get("product_id", "0x811e")
            return int(pid, 16) if isinstance(pid, str) else pid
        except:
            return 0x811e

    def _get_interface(self):
        """Get interface number"""
        return self.config.get("interface", 0)

    # -----------------------------
    # USB Device Detection
    # -----------------------------
    def _check_usb_device(self):
        """Check if USB device is connected using lsusb"""
        try:
            vid = self.config.get("vendor_id", "0x0fe6").replace("0x", "").lower()
            pid = self.config.get("product_id", "0x811e").replace("0x", "").lower()
            search_pattern = f"{vid}:{pid}"
            
            result = subprocess.run(
                ["lsusb"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return search_pattern in result.stdout.lower()
        except Exception:
            return False

    def _start_usb_monitor(self):
        """Start periodic USB device monitoring"""
        self._update_usb_status()

    def _update_usb_status(self):
        """Update USB connection status"""
        def check():
            connected = self._check_usb_device()
            self.after(0, lambda: self._set_device_status(connected))
        
        # Run check in thread to avoid blocking UI
        threading.Thread(target=check, daemon=True).start()
        
        # Schedule next check in 3 seconds
        self.after(3000, self._update_usb_status)

    def _set_device_status(self, connected):
        """Update UI based on device connection status"""
        self.device_connected = connected
        if connected:
            self.status_dot.configure(fg_color=COLORS["success"])
            self.status_label.configure(text="Connected", text_color=COLORS["success"])
        else:
            self.status_dot.configure(fg_color=COLORS["accent"])
            self.status_label.configure(text="Disconnected", text_color=COLORS["accent"])
            # Reset printer connection if device disconnected
            if self.printer is not None:
                try:
                    self.printer.close()
                except:
                    pass
                self.printer = None

    # -----------------------------
    # Printer connection
    # -----------------------------
    def connect_printer(self):
        if self.printer is not None:
            return True
            
        try:
            self.printer = Usb(
                self._get_vendor_id(),
                self._get_product_id(),
                self._get_interface()
            )
            self._set_device_status(True)
            return True
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: _make_popup(self, "Connection Error", f"Gagal terhubung ke printer:\n{err_msg}", "error"))
            self.printer = None
            return False

    def _update_status(self, status):
        if status == "connected":
            self.status_dot.configure(fg_color=COLORS["success"])
            self.status_label.configure(text="Connected", text_color=COLORS["success"])
        else:
            self.status_dot.configure(fg_color=COLORS["accent"])
            self.status_label.configure(text="Disconnected", text_color=COLORS["accent"])

    # -----------------------------
    # Settings Window
    # -----------------------------
    def _open_settings(self):
        """Open configuration window"""
        settings_win = ctk.CTkToplevel(self)
        settings_win.title("Settings")
        settings_win.geometry("450x400")
        settings_win.configure(fg_color=COLORS["bg_dark"])
        settings_win.wait_visibility()
        settings_win.grab_set()
        settings_win.resizable(False, False)

        # Title
        title = ctk.CTkLabel(
            settings_win,
            text="PRINTER CONFIGURATION",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        title.pack(pady=(SPACE["xxl"], SPACE["xl"]))

        # Settings container
        settings_frame = ctk.CTkFrame(settings_win, fg_color=COLORS["bg_card"], corner_radius=SPACE["md"])
        settings_frame.pack(fill="x", padx=SPACE["xxl"], pady=(0, SPACE["xl"]))

        settings_inner = ctk.CTkFrame(settings_frame, fg_color="transparent")
        settings_inner.pack(fill="x", padx=SPACE["xl"], pady=SPACE["xl"])

        # Vendor ID
        vid_frame = ctk.CTkFrame(settings_inner, fg_color="transparent")
        vid_frame.pack(fill="x", pady=SPACE["sm"])
        
        vid_label = ctk.CTkLabel(
            vid_frame,
            text="VENDOR ID",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["text_secondary"],
            width=120,
            anchor="w"
        )
        vid_label.pack(side="left")
        
        vid_entry = ctk.CTkEntry(
            vid_frame,
            width=200,
            height=SPACE["xxl"],
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            corner_radius=SPACE["xs"]
        )
        vid_entry.pack(side="right")
        vid_entry.insert(0, self.config.get("vendor_id", "0x0fe6"))

        # Product ID
        pid_frame = ctk.CTkFrame(settings_inner, fg_color="transparent")
        pid_frame.pack(fill="x", pady=SPACE["sm"])
        
        pid_label = ctk.CTkLabel(
            pid_frame,
            text="PRODUCT ID",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["text_secondary"],
            width=120,
            anchor="w"
        )
        pid_label.pack(side="left")
        
        pid_entry = ctk.CTkEntry(
            pid_frame,
            width=200,
            height=SPACE["xxl"],
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            corner_radius=SPACE["xs"]
        )
        pid_entry.pack(side="right")
        pid_entry.insert(0, self.config.get("product_id", "0x811e"))

        # Interface
        iface_frame = ctk.CTkFrame(settings_inner, fg_color="transparent")
        iface_frame.pack(fill="x", pady=SPACE["sm"])
        
        iface_label = ctk.CTkLabel(
            iface_frame,
            text="INTERFACE",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["text_secondary"],
            width=120,
            anchor="w"
        )
        iface_label.pack(side="left")
        
        iface_entry = ctk.CTkEntry(
            iface_frame,
            width=200,
            height=SPACE["xxl"],
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            corner_radius=SPACE["xs"]
        )
        iface_entry.pack(side="right")
        iface_entry.insert(0, str(self.config.get("interface", 0)))

        # Help text
        help_frame = ctk.CTkFrame(settings_win, fg_color=COLORS["bg_card"], corner_radius=SPACE["md"])
        help_frame.pack(fill="x", padx=SPACE["xxl"], pady=(0, SPACE["xl"]))

        help_inner = ctk.CTkFrame(help_frame, fg_color="transparent")
        help_inner.pack(fill="x", padx=SPACE["lg"], pady=SPACE["lg"])

        help_title = ctk.CTkLabel(
            help_inner,
            text="HOW TO FIND PRINTER ID",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["warning"]
        )
        help_title.pack(anchor="w")

        help_text = ctk.CTkLabel(
            help_inner,
            text="Run 'lsusb' in terminal to list USB devices.\nFormat: Bus XXX Device XXX: ID vendor:product",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
            justify="left"
        )
        help_text.pack(anchor="w", pady=(SPACE["xs"], 0))

        # Buttons
        btn_frame = ctk.CTkFrame(settings_win, fg_color="transparent")
        btn_frame.pack(fill="x", padx=SPACE["xxl"], pady=(0, SPACE["xxl"]))

        def save_settings():
            # Validate and save
            new_vid = vid_entry.get().strip()
            new_pid = pid_entry.get().strip()
            new_iface = iface_entry.get().strip()
            
            # Validate hex format
            try:
                if not new_vid.startswith("0x"):
                    new_vid = "0x" + new_vid
                int(new_vid, 16)
            except:
                _make_popup(settings_win, "Invalid Input", "Vendor ID harus dalam format hex (contoh: 0x0fe6)", "error")
                return
            
            try:
                if not new_pid.startswith("0x"):
                    new_pid = "0x" + new_pid
                int(new_pid, 16)
            except:
                _make_popup(settings_win, "Invalid Input", "Product ID harus dalam format hex (contoh: 0x811e)", "error")
                return
            
            try:
                new_iface = int(new_iface)
            except:
                _make_popup(settings_win, "Invalid Input", "Interface harus berupa angka (contoh: 0)", "error")
                return
            
            # Update config
            self.config["vendor_id"] = new_vid
            self.config["product_id"] = new_pid
            self.config["interface"] = new_iface
            
            # Reset printer connection
            if self.printer is not None:
                try:
                    self.printer.close()
                except:
                    pass
                self.printer = None
            
            # Save to file
            if save_config(self.config):
                _make_popup(settings_win, "Success", "Konfigurasi berhasil disimpan.", "success")
                settings_win.after(1500, settings_win.destroy)
            else:
                _make_popup(settings_win, "Error", "Gagal menyimpan konfigurasi.", "error")

        save_btn = ctk.CTkButton(
            btn_frame,
            text="Save",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            height=SPACE["xxl"] + SPACE["md"],
            corner_radius=SPACE["sm"],
            command=save_settings
        )
        save_btn.pack(side="left", fill="x", expand=True, padx=(0, SPACE["sm"]))

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["border"],
            hover_color=COLORS["bg_sidebar"],
            height=SPACE["xxl"] + SPACE["md"],
            corner_radius=SPACE["sm"],
            command=settings_win.destroy
        )
        cancel_btn.pack(side="right", fill="x", expand=True, padx=(SPACE["sm"], 0))

    # -----------------------------
    # UI
    # -----------------------------
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ===== SIDEBAR =====
        sidebar_width = 233
        sidebar = ctk.CTkFrame(self, fg_color=COLORS["bg_sidebar"], width=sidebar_width, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        # Brand
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=SPACE["xl"], pady=(SPACE["xxl"], SPACE["xl"]))
        
        brand_text = ctk.CTkLabel(
            brand_frame,
            text="PrinterPro",
            font=ctk.CTkFont(family="Segoe UI", size=SPACE["xl"], weight="bold"),
            text_color=COLORS["text_primary"]
        )
        brand_text.pack(side="left")
        
        version_label = ctk.CTkLabel(
            brand_frame,
            text="v1.0",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_secondary"]
        )
        version_label.pack(side="left", padx=(SPACE["sm"], 0), pady=(SPACE["sm"], 0))

        # Divider
        divider = ctk.CTkFrame(sidebar, fg_color=COLORS["border"], height=1)
        divider.pack(fill="x", padx=SPACE["xl"], pady=(0, SPACE["xl"]))

        # Navigation buttons
        self.nav_buttons = {}
        nav_items = [
            ("Dashboard", "dashboard"),
            ("Manual Mode", "manual"),
            ("Auto Mode", "auto"),
        ]

        for text, key in nav_items:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                anchor="w",
                font=ctk.CTkFont(size=14),
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
                hover_color=COLORS["bg_card"],
                height=SPACE["xxl"] + SPACE["md"],
                corner_radius=SPACE["sm"],
                command=lambda k=key: self._nav_click(k)
            )
            btn.pack(fill="x", padx=SPACE["lg"], pady=SPACE["xs"])
            self.nav_buttons[key] = btn

        self._set_nav_active("dashboard")

        # Spacer
        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Settings button
        settings_btn = ctk.CTkButton(
            sidebar,
            text="Settings",
            anchor="w",
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_card"],
            height=SPACE["xxl"] + SPACE["md"],
            corner_radius=SPACE["sm"],
            command=self._open_settings
        )
        settings_btn.pack(fill="x", padx=SPACE["lg"], pady=SPACE["xs"])

        # Status section
        status_frame = ctk.CTkFrame(sidebar, fg_color=COLORS["bg_card"], corner_radius=SPACE["md"])
        status_frame.pack(fill="x", padx=SPACE["lg"], pady=(SPACE["md"], SPACE["xl"]))

        status_inner = ctk.CTkFrame(status_frame, fg_color="transparent")
        status_inner.pack(fill="x", padx=SPACE["lg"], pady=SPACE["lg"])

        status_title = ctk.CTkLabel(
            status_inner,
            text="DEVICE STATUS",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        status_title.pack(anchor="w")

        status_row = ctk.CTkFrame(status_inner, fg_color="transparent")
        status_row.pack(fill="x", pady=(SPACE["sm"], 0))

        self.status_dot = ctk.CTkFrame(
            status_row, 
            fg_color=COLORS["accent"], 
            width=SPACE["md"], 
            height=SPACE["md"], 
            corner_radius=SPACE["sm"]
        )
        self.status_dot.pack(side="left")

        self.status_label = ctk.CTkLabel(
            status_row,
            text="Checking...",
            font=ctk.CTkFont(size=SPACE["lg"], weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        self.status_label.pack(side="left", padx=(SPACE["md"], 0))

        # Device ID display
        vid = self.config.get("vendor_id", "0x0fe6")
        pid = self.config.get("product_id", "0x811e")
        device_id_label = ctk.CTkLabel(
            status_inner,
            text=f"ID: {vid}:{pid}",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_secondary"]
        )
        device_id_label.pack(anchor="w", pady=(SPACE["xs"], 0))

        # ===== MAIN CONTENT =====
        main_content = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"], corner_radius=0)
        main_content.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        main_content.grid_columnconfigure(0, weight=1)
        main_content.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(main_content, fg_color="transparent", height=SPACE["xxxl"] + SPACE["lg"])
        header.grid(row=0, column=0, sticky="ew", padx=SPACE["xxl"], pady=(SPACE["xxl"], 0))

        self.header_title = ctk.CTkLabel(
            header,
            text="Dashboard",
            font=ctk.CTkFont(family="Segoe UI", size=SPACE["xl"] + SPACE["sm"], weight="bold"),
            text_color=COLORS["text_primary"]
        )
        self.header_title.pack(side="left")

        self.header_subtitle = ctk.CTkLabel(
            header,
            text="Overview & Quick Actions",
            font=ctk.CTkFont(size=SPACE["lg"]),
            text_color=COLORS["text_secondary"]
        )
        self.header_subtitle.pack(side="left", padx=(SPACE["lg"], 0), pady=(SPACE["sm"], 0))

        # Content area
        self.content_frame = ctk.CTkFrame(main_content, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=SPACE["xxl"], pady=SPACE["xxl"])
        self.content_frame.grid_columnconfigure((0, 1), weight=1)
        self.content_frame.grid_rowconfigure((0, 1), weight=1)

        self._show_dashboard()

    def _nav_click(self, key):
        self._set_nav_active(key)
        
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        if key == "dashboard":
            self.header_title.configure(text="Dashboard")
            self.header_subtitle.configure(text="Overview & Quick Actions")
            self._show_dashboard()
        elif key == "manual":
            self.header_title.configure(text="Manual Mode")
            self.header_subtitle.configure(text="Add counts manually and print")
            self.current_mode = "Manual"
            self._show_manual()
        elif key == "auto":
            self.header_title.configure(text="Auto Mode")
            self.header_subtitle.configure(text="Automatic counting with configurable settings")
            self.current_mode = "Auto"
            self._show_auto()

    def _set_nav_active(self, active_key):
        for key, btn in self.nav_buttons.items():
            if key == active_key:
                btn.configure(fg_color=COLORS["accent"], text_color=COLORS["text_primary"])
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_secondary"])

    def _show_dashboard(self):
        stats_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        stats_frame.grid(row=0, column=0, columnspan=2, sticky="new", pady=(0, SPACE["xl"]))
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)

        card1 = self._create_stat_card(stats_frame, "COUNT", "Current Count", str(self.counter), COLORS["accent"])
        card1.grid(row=0, column=0, sticky="ew", padx=(0, SPACE["md"]))

        card2 = self._create_stat_card(stats_frame, "MODE", "Active Mode", self.current_mode, COLORS["warning"])
        card2.grid(row=0, column=1, sticky="ew", padx=SPACE["md"])

        status_text = "Connected" if self.device_connected else "Disconnected"
        card3 = self._create_stat_card(stats_frame, "STATUS", "Device", status_text, COLORS["success"] if self.device_connected else COLORS["accent"])
        card3.grid(row=0, column=2, sticky="ew", padx=(SPACE["md"], 0))

        actions_card = ctk.CTkFrame(self.content_frame, fg_color=COLORS["bg_card"], corner_radius=SPACE["md"])
        actions_card.grid(row=1, column=0, columnspan=2, sticky="nsew")

        actions_title = ctk.CTkLabel(
            actions_card,
            text="QUICK ACTIONS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        actions_title.pack(anchor="w", padx=SPACE["xl"], pady=(SPACE["xl"], SPACE["lg"]))

        actions_inner = ctk.CTkFrame(actions_card, fg_color="transparent")
        actions_inner.pack(fill="x", padx=SPACE["xl"], pady=(0, SPACE["xl"]))
        actions_inner.grid_columnconfigure((0, 1), weight=1)

        test_btn = ctk.CTkButton(
            actions_inner,
            text="Test Connection",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            height=SPACE["xxxl"],
            corner_radius=SPACE["sm"],
            command=self._safe_test_print_call
        )
        test_btn.grid(row=0, column=0, sticky="ew", padx=(0, SPACE["md"]), pady=SPACE["sm"])

        print_btn = ctk.CTkButton(
            actions_inner,
            text="Print Receipt",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            height=SPACE["xxxl"],
            corner_radius=SPACE["sm"],
            command=self._safe_print_call
        )
        print_btn.grid(row=0, column=1, sticky="ew", padx=(SPACE["md"], 0), pady=SPACE["sm"])

    def _create_stat_card(self, parent, label, title, value, color):
        card_height = int(SPACE["xxxl"] * PHI) + SPACE["xl"]
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=SPACE["md"], height=card_height)
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=SPACE["xl"], pady=SPACE["lg"])

        label_lbl = ctk.CTkLabel(
            inner, 
            text=label,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=color
        )
        label_lbl.pack(anchor="w")

        title_lbl = ctk.CTkLabel(
            inner, text=title,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"]
        )
        title_lbl.pack(anchor="w", pady=(SPACE["sm"], SPACE["xs"]))

        value_lbl = ctk.CTkLabel(
            inner, text=value,
            font=ctk.CTkFont(size=SPACE["xl"], weight="bold"),
            text_color=COLORS["text_primary"]
        )
        value_lbl.pack(anchor="w")

        return card

    def _show_manual(self):
        counter_card = ctk.CTkFrame(self.content_frame, fg_color=COLORS["bg_card"], corner_radius=SPACE["md"])
        counter_card.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, SPACE["lg"]))

        counter_inner = ctk.CTkFrame(counter_card, fg_color="transparent")
        counter_inner.pack(expand=True)

        counter_title = ctk.CTkLabel(
            counter_inner,
            text="COUNTER",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        counter_title.pack(pady=(SPACE["xxl"], SPACE["md"]))

        self.manual_counter_label = ctk.CTkLabel(
            counter_inner,
            text=str(self.counter),
            font=ctk.CTkFont(family="Consolas", size=89, weight="bold"),
            text_color=COLORS["accent"]
        )
        self.manual_counter_label.pack()

        btn_frame = ctk.CTkFrame(counter_inner, fg_color="transparent")
        btn_frame.pack(pady=(SPACE["xl"], SPACE["xxl"]))

        btn_width = 144
        btn_height = SPACE["xxxl"]

        add_btn = ctk.CTkButton(
            btn_frame,
            text="+ Add",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            width=btn_width,
            height=btn_height,
            corner_radius=SPACE["sm"],
            command=self._manual_add
        )
        add_btn.pack(side="left", padx=SPACE["md"])

        reset_btn = ctk.CTkButton(
            btn_frame,
            text="Reset",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLORS["border"],
            hover_color=COLORS["bg_sidebar"],
            width=btn_width,
            height=btn_height,
            corner_radius=SPACE["sm"],
            command=self._reset_counter
        )
        reset_btn.pack(side="left", padx=SPACE["md"])

        print_btn = ctk.CTkButton(
            btn_frame,
            text="Print",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            width=btn_width,
            height=btn_height,
            corner_radius=SPACE["sm"],
            command=self._safe_print_call
        )
        print_btn.pack(side="left", padx=SPACE["md"])

    def _show_auto(self):
        auto_card = ctk.CTkFrame(self.content_frame, fg_color=COLORS["bg_card"], corner_radius=SPACE["md"])
        auto_card.grid(row=0, column=0, columnspan=2, sticky="nsew")

        auto_inner = ctk.CTkFrame(auto_card, fg_color="transparent")
        auto_inner.pack(expand=True)

        auto_title = ctk.CTkLabel(
            auto_inner,
            text="AUTO COUNTER",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        auto_title.pack(pady=(SPACE["xl"], SPACE["md"]))

        settings_frame = ctk.CTkFrame(auto_inner, fg_color=COLORS["bg_dark"], corner_radius=SPACE["sm"])
        settings_frame.pack(fill="x", padx=SPACE["xxl"], pady=(0, SPACE["lg"]))

        settings_inner = ctk.CTkFrame(settings_frame, fg_color="transparent")
        settings_inner.pack(pady=SPACE["lg"], padx=SPACE["lg"])

        max_frame = ctk.CTkFrame(settings_inner, fg_color="transparent")
        max_frame.pack(side="left", padx=SPACE["xl"])

        max_label = ctk.CTkLabel(
            max_frame,
            text="MAX COUNT",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        max_label.pack(anchor="w")

        self.max_count_entry = ctk.CTkEntry(
            max_frame,
            width=89,
            height=SPACE["xxl"],
            font=ctk.CTkFont(size=14),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            justify="center",
            corner_radius=SPACE["xs"]
        )
        self.max_count_entry.pack(pady=(SPACE["xs"], 0))
        self.max_count_entry.insert(0, str(self.auto_max_count))

        interval_frame = ctk.CTkFrame(settings_inner, fg_color="transparent")
        interval_frame.pack(side="left", padx=SPACE["xl"])

        interval_label = ctk.CTkLabel(
            interval_frame,
            text="INTERVAL (SEC)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        interval_label.pack(anchor="w")

        self.interval_entry = ctk.CTkEntry(
            interval_frame,
            width=89,
            height=SPACE["xxl"],
            font=ctk.CTkFont(size=14),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            justify="center",
            corner_radius=SPACE["xs"]
        )
        self.interval_entry.pack(pady=(SPACE["xs"], 0))
        self.interval_entry.insert(0, str(self.auto_interval))

        self.auto_counter_label = ctk.CTkLabel(
            auto_inner,
            text=str(self.counter),
            font=ctk.CTkFont(family="Consolas", size=89, weight="bold"),
            text_color=COLORS["warning"]
        )
        self.auto_counter_label.pack(pady=(SPACE["md"], 0))

        self.progress_label = ctk.CTkLabel(
            auto_inner,
            text="Ready to start",
            font=ctk.CTkFont(size=SPACE["lg"]),
            text_color=COLORS["text_secondary"]
        )
        self.progress_label.pack(pady=(SPACE["md"], SPACE["lg"]))

        self.progress_bar = ctk.CTkProgressBar(
            auto_inner,
            width=377,
            height=SPACE["md"],
            fg_color=COLORS["border"],
            progress_color=COLORS["warning"],
            corner_radius=SPACE["xs"]
        )
        self.progress_bar.pack(pady=(0, SPACE["lg"]))
        self.progress_bar.set(0)

        self.btn_auto = ctk.CTkButton(
            auto_inner,
            text="Start",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            width=200,
            height=SPACE["xxxl"],
            corner_radius=SPACE["sm"],
            command=self._toggle_auto
        )
        self.btn_auto.pack(pady=(0, SPACE["xl"]))

    def _reset_counter(self):
        self.counter = 0
        if hasattr(self, 'manual_counter_label') and self.manual_counter_label.winfo_exists():
            self.manual_counter_label.configure(text="0")

    def _update_label(self):
        if hasattr(self, 'manual_counter_label') and self.manual_counter_label.winfo_exists():
            self.manual_counter_label.configure(text=str(self.counter))
        if hasattr(self, 'auto_counter_label') and self.auto_counter_label.winfo_exists():
            self.auto_counter_label.configure(text=str(self.counter))

    def _manual_add(self):
        self.counter += 1
        self._update_label()

    def _toggle_auto(self):
        if not self.auto_running:
            try:
                max_count = int(self.max_count_entry.get())
                if max_count < 1:
                    max_count = 1
                self.auto_max_count = max_count
            except (ValueError, AttributeError):
                self.auto_max_count = 10
            
            try:
                interval = float(self.interval_entry.get())
                if interval < 0.1:
                    interval = 0.1
                self.auto_interval = interval
            except (ValueError, AttributeError):
                self.auto_interval = 1.0
            
            if hasattr(self, 'max_count_entry') and self.max_count_entry.winfo_exists():
                self.max_count_entry.configure(state="disabled")
            if hasattr(self, 'interval_entry') and self.interval_entry.winfo_exists():
                self.interval_entry.configure(state="disabled")
            
            self.auto_running = True
            self.counter = 0
            self._update_label()
            self._stopped_by_user = False
            with self._ui_lock:
                self.print_scheduled = False
            self.btn_auto.configure(
                text="Stop", 
                fg_color=COLORS["accent"], 
                hover_color=COLORS["accent_hover"]
            )
            self.progress_label.configure(text=f"Counting to {self.auto_max_count}...", text_color=COLORS["warning"])
            t = threading.Thread(target=self._auto_worker, daemon=True)
            t.start()
            self.auto_thread = t
        else:
            self._stopped_by_user = True
            self.auto_running = False
            self.btn_auto.configure(state="disabled")

    def _auto_worker(self):
        try:
            i = 0
            max_count = self.auto_max_count
            interval = self.auto_interval
            
            while self.auto_running and i < max_count:
                i += 1
                self.after(0, lambda v=i, m=max_count: self._set_counter_from_thread(v, m))
                time.sleep(interval)

            with self._ui_lock:
                if not self.print_scheduled:
                    self.print_scheduled = True
                    self.after(0, self._print_and_reset)
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: _make_popup(self, "Auto Error", f"Terjadi error pada proses otomatis:\n{err_msg}", "error"))
        finally:
            self.auto_running = False
            self.after(0, self._auto_cleanup_ui)

    def _print_and_reset(self):
        self._safe_print_call()
        self.counter = 0
        self._update_label()
        if hasattr(self, 'progress_bar') and self.progress_bar.winfo_exists():
            self.progress_bar.set(0)

    def _set_counter_from_thread(self, v, max_count=10):
        self.counter = v
        self._update_label()
        if hasattr(self, 'progress_bar') and self.progress_bar.winfo_exists():
            self.progress_bar.set(v / max_count)
        if hasattr(self, 'progress_label') and self.progress_label.winfo_exists():
            self.progress_label.configure(text=f"Counting: {v}/{max_count}")

    def _auto_cleanup_ui(self):
        try:
            if hasattr(self, 'max_count_entry') and self.max_count_entry.winfo_exists():
                self.max_count_entry.configure(state="normal")
            if hasattr(self, 'interval_entry') and self.interval_entry.winfo_exists():
                self.interval_entry.configure(state="normal")
            
            if hasattr(self, 'btn_auto') and self.btn_auto.winfo_exists():
                self.btn_auto.configure(
                    state="normal", 
                    text="Start",
                    fg_color=COLORS["success"],
                    hover_color=COLORS["success_hover"]
                )
            if hasattr(self, 'progress_label') and self.progress_label.winfo_exists():
                self.progress_label.configure(text="Complete", text_color=COLORS["success"])
        except Exception:
            pass

    def _safe_print_call(self):
        if threading.current_thread() is threading.main_thread():
            self.print_count()
        else:
            self.after(0, self.print_count)

    def _safe_test_print_call(self):
        if threading.current_thread() is threading.main_thread():
            self.test_print()
        else:
            self.after(0, self.test_print)

    def print_count(self):
        if not self.print_lock.acquire(blocking=False):
            _make_popup(self, "Info", "Proses cetak sedang berjalan. Mohon tunggu.", "info")
            return

        try:
            if not self.connect_printer():
                return

            p = self.printer
            ts = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            order_id = int(time.time())

            try:
                p.set(align="center", width=2, height=2)
            except Exception:
                try:
                    p.set(align="center")
                except Exception:
                    pass

            try:
                p._raw(b'\x1b\x45\x01')
                p.text("LAPORAN HITUNGAN\n")
                p._raw(b'\x1b\x45\x00')
            except Exception:
                p.text("LAPORAN HITUNGAN\n")

            try:
                p.set(width=1, height=1)
            except Exception:
                pass

            p.text("-------------------------\n\n")

            p.set(align="left")
            p.text(f"Tanggal : {ts}\n")
            p.text(f"Nomor   : #{order_id}\n")
            p.text("-------------------------\n")

            try:
                p._raw(b'\x1b\x45\x01')
                p.text(f"Hasil Hitungan : {self.counter}\n")
                p._raw(b'\x1b\x45\x00')
            except Exception:
                p.text(f"Hasil Hitungan : {self.counter}\n")

            p.text("-------------------------\n\n")

            p.set(align="center")
            p.text("Terima kasih!\n")
            p.text("Dicetak oleh PrinterPro\n\n")

            try:
                p.cut()
            except Exception:
                pass

            _make_popup(self, "Success", "Struk berhasil dicetak.", "success")
        except Exception as e:
            err_msg = str(e)
            _make_popup(self, "Print Error", f"Gagal mencetak:\n{err_msg}", "error")
        finally:
            try:
                self.print_lock.release()
            except Exception:
                pass

    def test_print(self):
        if not self.print_lock.acquire(blocking=False):
            _make_popup(self, "Info", "Proses cetak sedang berjalan. Mohon tunggu.", "info")
            return

        try:
            if not self.connect_printer():
                return

            p = self.printer
            ts = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

            try:
                p.set(align="center", width=2, height=2)
            except Exception:
                try:
                    p.set(align="center")
                except Exception:
                    pass

            try:
                p._raw(b'\x1b\x45\x01')
                p.text("TEST PRINT\n")
                p._raw(b'\x1b\x45\x00')
            except Exception:
                p.text("TEST PRINT\n")

            p.text("---------------------\n\n")
            p.set(align="left")
            p.text(f"Waktu : {ts}\n")
            p.text("Printer: BT-58D\n")
            p.text("Status : OK\n\n")
            p.set(align="center")
            p._raw(b'\x1b\x45\x01')
            p.text("Test berhasil!\n")
            p._raw(b'\x1b\x45\x00')
            p.text("\n")

            try:
                p.cut()
            except Exception:
                pass

            _make_popup(self, "Success", "Test print berhasil.", "success")
        except Exception as e:
            err_msg = str(e)
            _make_popup(self, "Print Error", f"Gagal mencetak:\n{err_msg}", "error")
        finally:
            try:
                self.print_lock.release()
            except Exception:
                pass

# -------------------------------
# Run
# -------------------------------
if __name__ == "__main__":
    app = PrinterApp()
    app.mainloop()
