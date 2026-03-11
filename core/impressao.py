import win32print
import time

LARGURA = 48


def montar_ticket(texto):
    linhas = texto.split("\n")
    formatado = []

    for l in linhas:
        l = l.strip()

        if not l:
            formatado.append("")
            continue

        if len(l) > LARGURA:
            l = l[:LARGURA]

        formatado.append(l.center(LARGURA))

    ticket = "\n".join(formatado)
    ticket += "\n\n\n\n\n"

    return ticket


def imprimir_texto(texto):

    try:
        printer_name = win32print.GetDefaultPrinter()

        handle = win32print.OpenPrinter(printer_name)

        texto = montar_ticket(texto)
        dados = texto.encode("cp850", "replace")

        job_id = win32print.StartDocPrinter(
            handle,
            1,
            ("Pedido Lazer Sport", None, "RAW")
        )

        win32print.StartPagePrinter(handle)

        win32print.WritePrinter(handle, dados)

        win32print.EndPagePrinter(handle)
        win32print.EndDocPrinter(handle)

        confirmado = False
        inicio = time.time()

        while (time.time() - inicio) < 15:

            try:
                job_info = win32print.GetJob(handle, job_id, 1)
                status = job_info["Status"]

                if status & win32print.JOB_STATUS_ERROR:
                    win32print.SetJob(
                        handle,
                        job_id,
                        0,
                        None,
                        win32print.JOB_CONTROL_DELETE
                    )

                    win32print.ClosePrinter(handle)
                    return False, printer_name

            except:
                confirmado = True
                break

            time.sleep(1)

        win32print.ClosePrinter(handle)

        return confirmado, printer_name

    except Exception as e:
        print("Erro:", e)
        return False, "Desconhecida"