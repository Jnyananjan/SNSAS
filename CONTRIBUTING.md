# Contributing to Smart RFID Student Attendance System

Thank you for your interest in contributing to this open-source project! We welcome improvements, bug fixes, hardware support, and documentation updates.

## Development Workflow

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/espattendance.git
   cd espattendance
   ```

2. **Firmware Development (PlatformIO)**
   - Open the root folder in VS Code with the PlatformIO extension installed.
   - Use `firmware/include/config.h.example` to create your local `firmware/include/config.h` (never commit your personal Wi-Fi or API keys).
   - Compile using `pio run` in the `firmware` folder.

3. **Python Tools & Backend Development**
   - Create and activate a Python 3.10+ virtual environment:
     ```bash
     cd python_tools
     python -m venv venv
     source venv/bin/activate  # On Windows: venv\Scripts\activate
     pip install -r requirements.txt
     ```
   - Run tests before submitting changes:
     ```bash
     pytest tests/ -v
     ```

## Code Guidelines
- **Firmware**: Keep memory usage low; leverage ESP32-S3 PSRAM for graphics buffers where appropriate.
- **Python**: Follow PEP 8 guidelines and include unit tests for new logic.
- **Documentation**: If adding support for new displays (e.g. ILI9341) or RFID readers (PN532), update `docs/wiring_diagram.md` accordingly.

## Submitting Pull Requests
- Provide a clear PR title and summary of changes.
- Ensure all automated tests pass (`pytest`).
- Verify that no secret keys or personal credentials are included in the commit.

