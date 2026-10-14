import json
import os
import subprocess
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

hex_file_path = ""
auto_mode_active = False
busy = False  # идёт операция с программатором
capturing_hotkey = False
hotkey_binding = None

CLI = "STM32_Programmer_CLI.exe"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flash_gui_config.json")

RESET_MODES = {
    "Software (-rst)": "-rst",
    "Hardware (-hardRst)": "-hardRst",
    "Core (-coreReset)": "-coreReset",
}

config = {"hotkey": "space", "reset_mode": "Software (-rst)"}
try:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config.update(json.load(f))
except (OSError, ValueError):
    pass
if config["reset_mode"] not in RESET_MODES:
    config["reset_mode"] = "Software (-rst)"


def save_config():
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def ui(func, *args, **kwargs):
    """ Выполнить действие с виджетами в главном потоке """
    root.after(0, lambda: func(*args, **kwargs))


def set_status(text, color):
    ui(status_indicator.configure, text=text, fg_color=color)


def log_message(text):
    def _do():
        text_log.insert(tk.END, text + "\n")
        text_log.see(tk.END)
    ui(_do)


def clear_log():
    ui(lambda: text_log.delete("1.0", tk.END))


def run_cli(args):
    return subprocess.run(
        [CLI] + args, capture_output=True, text=True,
        encoding="utf-8", errors="ignore", creationflags=subprocess.CREATE_NO_WINDOW
    )


def select_file():
    global hex_file_path
    file = filedialog.askopenfilename(
        title="Выберите прошивку",
        filetypes=[("HEX files", "*.hex"), ("All files", "*.*")]
    )
    if file:
        hex_file_path = os.path.normpath(file)
        label_path.configure(text=f"Файл: {hex_file_path}", text_color=("black", "white"))
        log_message(f"Выбран файл: {hex_file_path}")
        set_status("ГОТОВ К ПРОШИВКЕ", "#808080")


def get_poll_interval():
    """ Безопасное получение интервала из GUI """
    try:
        val = float(entry_interval.get().replace(",", "."))
        return max(val, 0.1)  # Защита от слишком частого опроса
    except ValueError:
        return 1.0


def check_and_flash_logic():
    """ Логика фонового потока для авто-режима """
    set_status("ПОИСК УСТРОЙСТВА...", "#4B0082")
    cmd_connect = ["-c", "port=SWD", "freq=8000"]

    try:
        result = run_cli(cmd_connect)

        if "Device ID" in result.stdout:
            log_message("\n[Авто] Обнаружено устройство! Запуск прошивки...")
            run_programmer_sync()

            set_status("ОТКЛЮЧИТЕ ПЛАТУ", "#FF8C00")
            log_message("[Авто] Ожидание отключения платы...")

            while auto_mode_active:
                res_check = run_cli(cmd_connect)
                if "Device ID" not in res_check.stdout:
                    log_message("[Авто] Плата отключена. Готов к следующей.")
                    break
                time.sleep(get_poll_interval())

    except Exception as e:
        log_message(f"[Авто] Ошибка опроса: {str(e)}")


def auto_worker():
    """ Цикл опроса для авто-режима """
    while auto_mode_active:
        if not hex_file_path:
            log_message("[Авто] Ошибка: файл не выбран. Авто-режим остановлен.")
            ui(stop_auto_from_worker)
            break

        check_and_flash_logic()
        time.sleep(get_poll_interval())


def stop_auto_from_worker():
    var_auto.set(False)
    toggle_auto_mode()


def set_controls_enabled(enabled):
    state = "normal" if enabled else "disabled"
    for w in (btn_select, btn_flash, btn_rdp, btn_erase, btn_reset,
              entry_interval, combo_reset, btn_hotkey):
        w.configure(state=state)


def toggle_auto_mode():
    global auto_mode_active
    if var_auto.get():
        if not hex_file_path:
            messagebox.showwarning("Ошибка", "Сначала выберите .hex файл!")
            var_auto.set(False)
            return
        auto_mode_active = True
        set_controls_enabled(False)
        threading.Thread(target=auto_worker, daemon=True).start()
    else:
        auto_mode_active = False
        set_controls_enabled(True)
        set_status("ГОТОВ К ПРОШИВКЕ", "#808080")
        log_message("[Авто] Авто-режим выключен.")


def run_programmer(event=None):
    """ Ручная прошивка: кнопка и горячая клавиша """
    if auto_mode_active or busy or capturing_hotkey:
        return
    if event is not None and isinstance(root.focus_get(), tk.Entry):
        return  # клавиша внутри поля ввода — не запускаем прошивку
    if not hex_file_path:
        messagebox.showwarning("Ошибка", "Сначала выберите .hex файл!")
        return
    threading.Thread(target=run_programmer_sync, daemon=True).start()


def run_programmer_sync():
    global busy
    busy = True
    set_status("ПРОШИВКА...", "#FFA500")
    clear_log()
    log_message(f"Запуск прошивки...\nПуть: {hex_file_path}")

    try:
        result = run_cli(["-c", "port=SWD", "freq=8000", "-w", hex_file_path, "--start"])

        if result.returncode == 0 and "successfully" in result.stdout.lower():
            set_status("ПРОШИВКА УСПЕШНА", "#00AA00")
            log_message("--- УСПЕШНО ---")
            log_message(result.stdout)
        else:
            set_status("ОШИБКА ПРОШИВКИ", "#CC0000")
            log_message("--- ОШИБКА ---")
            log_message(result.stdout)
            if result.stderr:
                log_message(result.stderr)
    except Exception as e:
        set_status("КРИТИЧЕСКАЯ ОШИБКА", "#CC0000")
        log_message(f"Ошибка выполнения: {str(e)}")
    finally:
        busy = False


def start_simple_op(busy_text, ok_text, err_text, args):
    """ Одиночная команда CLI в фоне (RDP, стирание, reset) """
    if auto_mode_active or busy:
        return
    threading.Thread(target=simple_op_sync, args=(busy_text, ok_text, err_text, args), daemon=True).start()


def simple_op_sync(busy_text, ok_text, err_text, args):
    global busy
    busy = True
    set_status(busy_text, "#FFA500")
    clear_log()
    log_message(f"> {CLI} {' '.join(args)}")

    try:
        result = run_cli(args)
        log_message(result.stdout)
        if result.stderr:
            log_message(result.stderr)
        if result.returncode == 0 and "error" not in result.stdout.lower():
            set_status(ok_text, "#00AA00")
            log_message(f"--- {ok_text} ---")
        else:
            set_status(err_text, "#CC0000")
            log_message("--- ОШИБКА ---")
    except Exception as e:
        set_status("КРИТИЧЕСКАЯ ОШИБКА", "#CC0000")
        log_message(f"Ошибка выполнения: {str(e)}")
    finally:
        busy = False


def reset_rdp():
    start_simple_op("СБРОС RDP...", "RDP СБРОШЕН", "ОШИБКА СБРОСА RDP",
                    ["-c", "port=SWD", "-ob", "RDP=0xAA"])


def erase_flash():
    start_simple_op("ОЧИСТКА FLASH...", "FLASH ОЧИЩЕНА", "ОШИБКА ОЧИСТКИ FLASH",
                    ["-c", "port=SWD", "freq=8000", "-e", "all"])


def reset_mcu():
    flag = RESET_MODES[combo_reset.get()]
    start_simple_op("RESET...", "RESET ВЫПОЛНЕН", "ОШИБКА RESET",
                    ["-c", "port=SWD", "freq=8000", flag])


# Горячая клавиша
def apply_hotkey(keysym):
    global hotkey_binding
    new_binding = f"<KeyPress-{keysym}>"
    root.bind(new_binding, run_programmer)  # TclError при недопустимом keysym — до смены состояния
    if hotkey_binding and hotkey_binding != new_binding:
        root.unbind(hotkey_binding)
    hotkey_binding = new_binding
    config["hotkey"] = keysym
    save_config()
    btn_hotkey.configure(text=f"Клавиша: {keysym}")
    label_hint.configure(text=f"{keysym} — ручная прошивка (если авто-режим выключен)")


def start_capture_hotkey():
    global capturing_hotkey
    capturing_hotkey = True
    btn_hotkey.configure(text="Нажмите клавишу...")
    root.bind("<KeyPress>", finish_capture_hotkey)


def finish_capture_hotkey(event):
    global capturing_hotkey
    if not capturing_hotkey:
        return
    root.unbind("<KeyPress>")
    capturing_hotkey = False
    if event.keysym != "Escape":
        try:
            apply_hotkey(event.keysym)
            return
        except tk.TclError:
            pass
    btn_hotkey.configure(text=f"Клавиша: {config['hotkey']}")


def on_reset_mode_change(value):
    config["reset_mode"] = value
    save_config()


# GUI Setup
root = ctk.CTk()
root.title("STM32 Production Flasher")
root.geometry("720x720")

# Верхняя панель управления
frame_top = ctk.CTkFrame(root)
frame_top.pack(padx=10, pady=(10, 4), fill="x")

btn_select = ctk.CTkButton(frame_top, text="Обзор (.hex)", command=select_file, width=110)
btn_select.pack(side="left", padx=8, pady=8)

var_auto = ctk.BooleanVar()
chk_auto = ctk.CTkSwitch(frame_top, text="Авто-режим", variable=var_auto, command=toggle_auto_mode,
                         font=ctk.CTkFont(weight="bold"))
chk_auto.pack(side="left", padx=8)

ctk.CTkLabel(frame_top, text="Опрос (сек):").pack(side="left", padx=(12, 4))
entry_interval = ctk.CTkEntry(frame_top, width=60, justify="center")
entry_interval.insert(0, "1.0")
entry_interval.pack(side="left")

btn_hotkey = ctk.CTkButton(frame_top, text="", command=start_capture_hotkey, width=140,
                           fg_color="#555555", hover_color="#444444")
btn_hotkey.pack(side="right", padx=8)

# Панель действий
frame_actions = ctk.CTkFrame(root)
frame_actions.pack(padx=10, pady=4, fill="x")

btn_flash = ctk.CTkButton(frame_actions, text="Прошить", command=run_programmer, width=100,
                          fg_color="#2E8B57", hover_color="#236B43")
btn_flash.pack(side="left", padx=8, pady=8)

btn_erase = ctk.CTkButton(frame_actions, text="Очистить flash", command=erase_flash, width=110,
                          fg_color="#B36B00", hover_color="#8F5600")
btn_erase.pack(side="left", padx=4)

btn_rdp = ctk.CTkButton(frame_actions, text="Сброс RDP", command=reset_rdp, width=100,
                        fg_color="#B33A3A", hover_color="#8F2E2E")
btn_rdp.pack(side="left", padx=4)

combo_reset = ctk.CTkOptionMenu(frame_actions, values=list(RESET_MODES),
                                command=on_reset_mode_change, width=170)
combo_reset.set(config["reset_mode"])
combo_reset.pack(side="right", padx=8)

btn_reset = ctk.CTkButton(frame_actions, text="Reset", command=reset_mcu, width=80)
btn_reset.pack(side="right", padx=4)

# Остальной интерфейс
label_path = ctk.CTkLabel(root, text="Файл не выбран", text_color="#E04040", wraplength=660)
label_path.pack(pady=5)

label_hint = ctk.CTkLabel(root, text="", font=ctk.CTkFont(slant="italic"))
label_hint.pack(pady=5)

status_indicator = ctk.CTkLabel(root, text="ОЖИДАНИЕ ФАЙЛА", fg_color="#808080", text_color="white",
                                font=ctk.CTkFont(size=22, weight="bold"), height=70, corner_radius=8)
status_indicator.pack(fill="x", padx=10, pady=5)

text_log = ctk.CTkTextbox(root, wrap="word", font=ctk.CTkFont(family="Consolas", size=13))
text_log.pack(padx=10, pady=10, fill="both", expand=True)

apply_hotkey(config["hotkey"])
root.mainloop()
