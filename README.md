# GUI Counting Printer BT-58D 🖨️

A professional desktop application for managing USB thermal receipt printers on Linux. Built with Python and CustomTkinter, featuring a modern dark UI with manual and automatic counting modes.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Linux-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- **Dashboard View** - Overview of current count, active mode, and device connection status
- **Manual Mode** - Add counts manually with increment, reset, and print buttons
- **Auto Mode** - Automatic counting with configurable max count and interval settings
- **USB Device Monitoring** - Real-time detection of printer connection status
- **Configurable Settings** - Set vendor ID, product ID, and interface for your USB printer
- **Test Print** - Quickly verify printer connectivity
- **Receipt Printing** - Generate formatted receipts with timestamps and order numbers

## Screenshots

The application features a sleek dark theme with:
- Sidebar navigation
- Real-time device status indicator
- Large counter display
- Progress bar for auto mode

## Requirements

- Python 3.8+
- Linux operating system (uses `lsusb` for device detection)
- USB thermal receipt printer (ESC/POS compatible)

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/project-print.git
   cd project-print
   ```

2. **Install dependencies**
   ```bash
   pip install customtkinter python-escpos pyusb
   ```

3. **Set up USB permissions (Linux)**
   
   Create a udev rule to allow access to your USB printer without root:
   ```bash
   sudo nano /etc/udev/rules.d/99-usb-printer.rules
   ```
   
   Add the following line (adjust vendor/product IDs as needed):
   ```
   SUBSYSTEM=="usb", ATTR{idVendor}=="0fe6", ATTR{idProduct}=="811e", MODE="0666"
   ```
   
   Reload udev rules:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

4. **Find your printer's USB IDs**
   ```bash
   lsusb
   ```
   Look for your thermal printer and note the `ID vendor:product` values.

## Usage

### Running the Application

```bash
python gui.py
```

### Navigation

- **Dashboard** - View statistics and quick actions
- **Manual Mode** - Manually increment counter and print receipts
- **Auto Mode** - Configure and run automatic counting
- **Settings** - Configure printer USB IDs

### Configuration

The application stores settings in `printer_config.json`:

```json
{
  "vendor_id": "0x0fe6",
  "product_id": "0x811e",
  "interface": 0,
  "auto_max_count": 10,
  "auto_interval": 1.0
}
```

| Setting | Description |
|---------|-------------|
| `vendor_id` | USB Vendor ID in hex format |
| `product_id` | USB Product ID in hex format |
| `interface` | USB interface number (usually 0) |
| `auto_max_count` | Default max count for auto mode |
| `auto_interval` | Default interval in seconds for auto mode |

## Project Structure

```
project-print/
├── gui.py           # Main application with GUI
├── main.py          # Simple print test script
├── usb-check.py     # USB device detection utility
├── printer_config.json  # Configuration file (auto-generated)
└── README.md
```

## Utility Scripts

### Test Print (`main.py`)
Quick test to verify printer communication:
```bash
python main.py
```

### USB Check (`usb-check.py`)
Check if your USB printer is detected:
```bash
python usb-check.py
```

## Troubleshooting

### Printer not detected
1. Ensure the printer is connected and powered on
2. Run `lsusb` to verify the device appears
3. Check that vendor/product IDs match in Settings
4. Verify udev rules are set up correctly

### Permission denied errors
- Ensure udev rules are configured (see Installation step 3)
- Alternatively, run with sudo (not recommended for regular use)

### Print quality issues
- Check paper roll is installed correctly
- Verify printer is ESC/POS compatible
- Try the test print function first

## Supported Printers

This application works with ESC/POS compatible thermal printers. Tested with:
- POS-58 series (58mm thermal printers)
- Most generic USB receipt printers

## Dependencies

| Package | Purpose |
|---------|---------|
| `customtkinter` | Modern UI framework |
| `python-escpos` | ESC/POS printer communication |
| `pyusb` | USB device access |

## License

MIT License - feel free to use and modify as needed.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

**GUI Counting Printer BT-58D v1.0** - Built with ❤️ for thermal printer enthusiasts

