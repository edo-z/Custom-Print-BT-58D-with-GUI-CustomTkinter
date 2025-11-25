import usb.core

dev = usb.core.find(idVendor=0x0fe6, idProduct=0x811e)
print("Device:", dev)
