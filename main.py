from escpos.printer import Usb

p = Usb(0x0fe6, 0x811e, 0)

p.text("POS58 USB Test OK!\n")
p.cut()


