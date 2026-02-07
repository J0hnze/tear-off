import win32print

flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
printers = win32print.EnumPrinters(flags)

print("Installed printers:\n")
for p in printers:
    # p[2] is the printer name
    name = p[2]
    try:
        h = win32print.OpenPrinter(name)
        info = win32print.GetPrinter(h, 2)  # level 2 includes PortName
        win32print.ClosePrinter(h)
        port = info["pPortName"]
    except Exception as e:
        port = f"(could not query port: {e})"
    print(f"- {name}  -->  {port}")