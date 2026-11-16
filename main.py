import flet as ft
import threading, queue, builtins, re

in_q = queue.Queue()
out_q = queue.Queue()

def custom_print(*args, sep=" ", end="\n", **kwargs):
    out_q.put(sep.join(str(a) for a in args) + end)

def custom_input(prompt=""):
    if prompt: out_q.put(str(prompt))
    return in_q.get()

builtins.print = custom_print
builtins.input = custom_input

URL_RE = re.compile(r"https?://\S+")

def main(page: ft.Page):
    page.title = "Тир"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 12
    page.scroll = ft.ScrollMode.AUTO

    output_box = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, expand=True)
    cmd_field = ft.TextField(
        hint_text="Введи запрос или команду...",
        expand=True,
        on_submit=lambda e: send_cmd(None)
    )

    def send_cmd(e):
        val = cmd_field.value
        cmd_field.value = ""
        page.update()
        out_q.put("> "+val+chr(10))
        in_q.put(val)

    def open_url(url):
        try:
            page.launch_url(url)
        except Exception:
            out_q.put("[Не удалось открыть браузер: "+url+"]"+chr(10))

    def make_line(txt):
        # если в строке есть URL — делаем его кликабельным
        urls = URL_RE.findall(txt)
        if not urls:
            return ft.Text(txt, selectable=True, size=14)
        parts = []
        last = 0
        for m in URL_RE.finditer(txt):
            if m.start() > last:
                parts.append(ft.TextSpan(txt[last:m.start()]))
            parts.append(ft.TextSpan(m.group(0), style=ft.TextStyle(color="#38BDF8", underline=True),
                                      link_url=m.group(0)))
            last = m.end()
        if last < len(txt):
            parts.append(ft.TextSpan(txt[last:]))
        return ft.RichText(spans=parts, size=14)

    send_btn = ft.IconButton(icon=ft.Icons.SEND, on_click=send_cmd)

    page.add(
        ft.Row([ft.Text("Браузер ТИР", size=20, weight=ft.FontWeight.BOLD)],
               alignment=ft.MainAxisAlignment.CENTER),
        ft.Container(content=output_box, expand=True, bgcolor="#161B22", border_radius=10, padding=10),
        ft.Row([cmd_field, send_btn])
    )

    def poll_output():
        while True:
            txt = out_q.get()
            for line in txt.split(chr(10)):
                if line == "" and len(output_box.controls) and output_box.controls[-1].value == "":
                    continue
                output_box.controls.append(make_line(line))
            if len(output_box.controls) > 200:
                del output_box.controls[:50]
            page.update()

    def run_tir():
        try:
            import tir_user
        except Exception as ex:
            out_q.put(chr(10)+"[Ошибка запуска]: "+str(ex)+chr(10))

    threading.Thread(target=poll_output, daemon=True).start()
    threading.Thread(target=run_tir, daemon=True).start()

ft.app(target=main)