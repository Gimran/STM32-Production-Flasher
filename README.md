# STM32 Production Flasher

A small Windows GUI around **STM32CubeProgrammer CLI** for flashing STM32 boards on a production line. Pick a `.hex` file, connect a board over SWD (ST-LINK) and flash it with one key press — or switch on auto mode and just swap boards.

Built with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).

## Features

- **Manual flash** — button or a hotkey (Space by default).
- **Auto mode** — polls the SWD bus, flashes a board as soon as it is detected, then waits for it to be disconnected before looking for the next one. The poll interval is configurable (minimum 0.1 s).
- **Erase flash** — full chip erase (`-e all`).
- **Reset RDP** — drops read-out protection back to Level 0 (`RDP=0xAA`). Note that lowering the protection level triggers a mass erase of the flash. There is no confirmation dialog.
- **Reset MCU** — with a selectable method: Software (`-rst`), Hardware (`-hardRst`) or Core (`-coreReset`). Hardware reset requires the NRST line to be wired to the ST-LINK.
- **Configurable hotkey** — click the *Key:* button and press the new key (Esc cancels).
- **Large status banner** and a live log with the full CLI output.
- Settings (hotkey, reset method) are stored in `flash_gui_config.json` next to the script.

## Requirements

- Windows
- Python 3.8+
- [STM32CubeProgrammer](https://www.st.com/en/development-tools/stm32cubeprog.html) — `STM32_Programmer_CLI.exe` must be on `PATH`
- An ST-LINK probe connected to the target over SWD

## Installation

```bash
git clone https://github.com/Gimran/STM32-Production-Flasher.git
cd STM32-Production-Flasher
pip install customtkinter
```

## Usage

```bash
python flash_gui2.py
```

1. Click **Browse (.hex)** and select the firmware.
2. Flash a board:
   - **Manual:** connect the board and press the hotkey (Space) or the **Flash** button.
   - **Auto:** enable the **Auto mode** switch. Connect a board → it is flashed → the banner asks you to disconnect it → connect the next one.
3. Use **Erase flash**, **Reset RDP** and **Reset** when needed. Utility buttons are disabled while auto mode is running.

The hotkey is ignored while the cursor is in the poll-interval field.

### CLI commands used

| Action | Command |
| --- | --- |
| Detect board | `STM32_Programmer_CLI.exe -c port=SWD freq=8000` |
| Flash | `STM32_Programmer_CLI.exe -c port=SWD freq=8000 -w <file.hex> --start` |
| Erase flash | `STM32_Programmer_CLI.exe -c port=SWD freq=8000 -e all` |
| Reset RDP | `STM32_Programmer_CLI.exe -c port=SWD -ob RDP=0xAA` |
| Reset | `STM32_Programmer_CLI.exe -c port=SWD freq=8000 -rst` / `-hardRst` / `-coreReset` |

## Configuration

`flash_gui_config.json` is created automatically:

```json
{
  "hotkey": "space",
  "reset_mode": "Software (-rst)"
}
```

The hotkey is a Tk key name (`space`, `F5`, `Return`, `a`, ...).

## Caution

*Reset RDP* and *Erase flash* wipe the target's flash memory immediately and without confirmation. Make sure the right board is connected.

## License

[MIT](LICENSE)
