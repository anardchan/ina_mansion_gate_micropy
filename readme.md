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

# System Overview


# How to debug using `rshell`
1. Run `rshell` in terminal.
2. Connect to board with .
    - `connect` command
        - format of `connect` command
        - `connect serial port [baud]`
3. Shortcut `rhsell --port [user port]`
4. Follow instructions to paste code and start debugging.

# Some Notes
## Ampy
You can use ampy for file management (list, put, get, etc.)