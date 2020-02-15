import base64
import pyfldigi
import functools
from pytun import TunTapDevice
import time

def get_byte_pair(integer):
    return divmod(integer, 0x100)

c = pyfldigi.Client()
c.main.squelch = True
c.main.squelch_level = 25
c.main.afc = False
c.modem.id = 90 # THOR100
c.modem.carrier = 2000
c.text.clear_rx()

tun = TunTapDevice()
tun.addr = '10.0.0.1'
tun.dstaddr = '10.8.0.2'
tun.netmask = '255.255.0.0'
tun.mtu = 200 # also 9 bytes for our wrapper
tun.up()

print("Ready")

while True:
    # process audio -> net
    c.text.get_rx_data()

    # process net -> audio
    data = tun.read(tun.mtu)
    data_len = len(data)
    b64data = str(base64.b64encode(bytearray(data)))
    b64data_len = len(b64data)
    data = "YYY" + hex(b64data_len)[2:4].zfill(2) + \
           b64data + \
           hex(functools.reduce(lambda a, b: a ^ b, data))[2:4].zfill(2) + \
           "ZZZ\nde  k\n^r"
    print("Trying to send: ")
    print(data)
    c.main.send(data)
    print("done sending (?)")
    time.sleep(1)
