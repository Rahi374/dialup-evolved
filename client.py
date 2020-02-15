import base64
import pyfldigi
import functools
from pytun import TunTapDevice
import time

def get_byte_pair(integer):
    return divmod(integer, 0x100)

def find_all_indexes(input_str, search_str):
    l1 = []
    length = len(input_str)
    index = 0
    while index < length:
        i = input_str.find(search_str, index)
        if i == -1:
            return l1
        l1.append(i)
        index = i + 1
    return l1

c = pyfldigi.Client()
c.main.squelch = True
c.main.squelch_level = 0
c.main.afc = False
#c.modem.id = 88 # THOR50x1
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

seq = 0
old_seq = -1
wake_up_time = time.time()
input_buf = b""

while True:
    cont_main_loop = False

    # process audio -> net
    print("Checking input; input buf = ")
    input_buf += c.text.get_rx_data()
    print(input_buf)
    starting_indices = find_all_indexes(input_buf, b'YYY')
    ending_indices = find_all_indexes(input_buf, b'ZZZ')
    for packet_num, begin_i in enumerate(starting_indices):
        if packet_num < len(ending_indices) and \
           ending_indices[packet_num] > begin_i:
           #(packet_num < len(starting_indices) - 1 or \
                   #ending_indices[packet_num] < starting_indices[packet_num + 1]):
            # this is a complete packet
            data_start_index = begin_i + 7
            data_len = int(chr(input_buf[begin_i + 5]) + chr(input_buf[begin_i + 6]), 16)
            packet = input_buf[data_start_index:(data_start_index+data_len+2+3)]
            raw_data = packet[2:-3]
            print(f"!!!!! CALCULATING RECVING CHECKSUM ON {raw_data}")
            calculated_checksum = functools.reduce(lambda a, b: a ^ b, raw_data)
            received_checksum = int(packet[-2:], 16)
            if calculated_checksum != received_checksum:
                print(f"CHECKSUM: declared {received_checksum}, calculated {calculated_checksum}")
                input_buf = b""
                cont_main_loop = True
                break
            packet = base64.b64decode(raw_data.decode("ascii"))
            print("Received packet! Contents:")
            print(packet)
            tun.write(packet)
        else:
            # this is an incomplete packet
            #old_seq = int(chr(input_buf[begin_i + 3]) + chr(input_buf[begin_i + 4]), 16)
            cont_main_loop = True

    if cont_main_loop or time.time() < wake_up_time:
        continue

    input_buf = b""

    # process net -> audio
    data = tun.read(tun.mtu)
    data_len = len(data)
    b64data = base64.b64encode(bytearray(data))
    b64data_len = len(b64data)
    print(f"!!!!! CALCULATING SENDING CHECKSUM ON {b64data}")
    data = "YYY" + hex(seq)[2:4].zfill(2) + hex(b64data_len)[2:4].zfill(2) + \
           str(b64data) + \
           hex(functools.reduce(lambda a, b: a ^ b, b64data))[2:4].zfill(2) + \
           "ZZZ\nde  k\n^r"
    print("Trying to send: ")
    print(data)
    c.main.send(data)
    print("done sending (?)")
    wake_up_time = time.time() + 8
    seq += 1
