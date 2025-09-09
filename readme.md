# System Overview

# How to debug:

## Using `rshell` and `ampy`:

1. From the command line, following `ampy --port <your_device_port> put <local_file_path> [<remote_file_path>]`
   - Explanation of arguments:
     - `--port <your_device_port>`: Specifies the serial port to which your MicroPython or CircuitPython board is connected. This is a required argument. Examples of port names include /dev/cu.usbserial-XXXX on macOS/Linux or COMX (e.g., COM3) on Windows.
     - `put`: This is the subcommand indicating that you want to upload a file.
     - `<local_file_path>`: The path to the file on your local computer that you want to upload.
     - `[<remote_file_path>]`: An optional argument to specify the path and filename on the board where you want to save the file. If omitted, the file will be saved in the root directory of the board's filesystem with the same filename as the local file.
   - Examples:
     - `ampy --port /dev/cu.usbserial-12345 put my_script.py`
     - `ampy --port /dev/cu.usbserial-12345 put my_script.py /scripts/remote_script.py`
   - Load the needed files on the target boards.
2. Run `rshell` in terminal using the command `rhsell --port <your_device_port>`
3. Run `repl` to run repl mode.
4. You can hit on `Ctrl+D` to soft reset the board. This should automatically run `main.py` that was loaded to the board.

# Hardware References

## Beninca Hardware

- [Beninca HEAD Manual L8542839](https://manuals.easygates.co.uk/PDF/beninca/Head_GBR3.pdf)
- [Beninca Swing Arm Manual L8542716](https://manuals.easygates.co.uk/PDF/misc/Bob_21ME__30ME_230v.pdf)

## ESP32

- [ESP32-DevKitC V4](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html)

## Break Sensor ABT-30 Aleph 100' Outdoor 200' Indoor Dual Twin Beam

- [ABT-30](https://dwg.us/ecommerce/pc/viewPrd.asp?idproduct=136576&srsltid=AfmBOopSMKv7vpceHVE2ciQFNJ_UvItQHwZyacHZCleJeYDmerh2W5Sm)

## SSD1306

- Used to gether with micropython
- SSD1306 module found [here](https://github.com/stlehmann/micropython-ssd1306/tree/master).

## MFRC522

- Used to gether with micropython
- MFRC522 module found [here](https://github.com/wendlers/micropython-mfrc522/tree/master).

# Software References

## Ampy

Ampy (Adafruit MicroPython Tool) is a command-line utility used to interact with MicroPython or CircuitPython boards over a serial connection.

Ampy is meant to be a simple command line tool to manipulate files and run code on a CircuitPython or MicroPython board over its serial connection. With ampy you can send files from your computer to the board's file system, download files from a board to your computer, and even send a Python script to a board to be executed.

Note that ampy by design is meant to be simple and does not support advanced interaction like a shell or terminal to send input to a board. Check out other MicroPython tools like rshell or mpfshell for more advanced interaction with boards.

Ampy resource found [here](https://github.com/scientifichackers/ampy)
