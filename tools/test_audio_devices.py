import sounddevice as sd

def find_usb_mic():
    devices = sd.query_devices()

    for i, dev in enumerate(devices):
        if "USB" in dev["name"]:
            return i

    return None

print(sd.query_devices())
print()
print("Default input device:")
print(sd.default.device)
print()
print("USB microphone device:")
print(find_usb_mic())