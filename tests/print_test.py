from escpos.printer import Win32Raw

PRINTER_NAME = "BIXOLON SRP-E300"  # must match Windows printer name exactly

p = Win32Raw(PRINTER_NAME)

# Center + bold + double size header
p.set(align="center", bold=True, double_width=True, double_height=True)
p.text("TALLY\n")

# Normal text
p.set(align="center", bold=False, double_width=False, double_height=False)
p.text("---------------------\n")
p.text("'s\n")
p.text("T\n")
p.text("\n")
p.text("---------------------\n")

# Footer
p.set(align="center")
# p.text("You got this.\n\n")

# Feed a bit then cut
p.text("\n\n")
p.cut()

p.close()
