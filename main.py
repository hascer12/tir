import flet as ft
import threading, queue, builtins

in_q = queue.Queue()
out_q = queue.Queue()

def custom_print(*args, sep=" ", end="\n", **kwargs):
    out_q.put(sep.join(str(a) for a in args) + end)

def custom_input(prompt=""):
    if prompt:
        out_q.put(str(prompt))
    return in_q.get()

builtins.print = custom_print
builtins.input = custom_input

def main(page: ft.Page):
    page.title = "Тир"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 12
    page.scroll = ft.ScrollMode.AUTO

    output_box = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)
    cmd_field = ft.TextField(
        hint_text="Введи запрос или команду...",
        expand=True,
        on_submit=lambda e: send_cmd(None)
    )

    def send_cmd(e):
        val = cmd_field.value
        cmd_field.value = ""
        page.update()
        out_q.put(f"> {val}\n")
        in_q.put(val)

    send_btn = ft.IconButton(icon=ft.Icons.SEND, on_click=send_cmd)

    page.add(
        ft.Row([ft.Text("Браузер ТИР", size=20, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER),
        ft.Container(content=output_box, expand=True, bgcolor="#161B22", border_radius=10, padding=10),
        ft.Row([cmd_field, send_btn])
    )

    def poll_output():
        while True:
            txt = out_q.get()
            output_box.controls.append(ft.Text(txt.rstrip("\n"), selectable=True, size=14))
            if len(output_box.controls) > 150:
                output_box.controls.pop(0)
            page.update()

    def run_tir():
        try:
            import tir_user
        except Exception as ex:
            out_q.put(f"\n[Ошибка запуска]: {ex}\n")

    threading.Thread(target=poll_output, daemon=True).start()
    threading.Thread(target=run_tir, daemon=True).start()

ft.app(target=main)
