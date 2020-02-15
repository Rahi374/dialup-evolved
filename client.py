import base64
import pyfldigi
import functools
from pytun import TunTapDevice
import scapy
import sys
import time

def send_packet(packet):
    ip = IP(packet)
    origin_ip = ip.src
    send(ip)

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

def handle_packet_client(packet):
    return

def handle_packet(packet):
    print("Handling packet")
    if i_am_server:
        send_packet(packet)
    else:
        tun.write(packet)

c = pyfldigi.Client()
c.main.squelch = True
c.main.squelch_level = 0
c.main.afc = False
c.modem.name = "DOMX88"
#c.modem.id = 11 # DOMX88
#c.modem.id = 28 # MFSK64L
#c.modem.id = 87 # THOR25x4
#c.modem.id = 88 # THOR50x1
#c.modem.id = 90 # THOR100
c.modem.carrier = 2100
c.text.clear_rx()

tun = TunTapDevice()
tun.addr = '10.0.0.1'
tun.dstaddr = '10.8.0.2'
tun.netmask = '255.255.0.0'
tun.mtu = 200 # also 9 bytes for our wrapper
tun.up()

print("Ready")

i_am_server = sys.argv[1] == "server"

seq = 0
old_seq = -1
wake_up_time = time.time()
input_buf = b""
origin_ip = "0.0.0.0"

def send_net_to_audio_server(scapy_packet):
    send_net_to_audio(bytes(scapy_packet))

def send_net_to_audio(data):
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
    wake_up_time = time.time() + 12
    seq += 1

while True:
    cont_main_loop = False

    # warning: does not work if multiple packets in one buffer

    # process audio -> net
    #print(f"Checking input; input buf type is {type(input_buf)}")
    d = c.text.get_rx_data()
    if type(d) is bytes:
        input_buf += d
    else: # is str
        input_buf += bytes(d, "ascii")
    #print(input_buf)
    starting_indices = find_all_indexes(input_buf, b'YYY')
    ending_indices = find_all_indexes(input_buf, b'ZZZ')
    if len(starting_indices) > 1:
        starting_indices = starting_indices[-1:]
    for packet_num, begin_i in enumerate(starting_indices):
        if packet_num < len(ending_indices) and \
           ending_indices[packet_num] > begin_i:
            # this is a complete packet
            try:
                data_start_index = begin_i + 7
                data_len = int(chr(input_buf[begin_i + 5]) + chr(input_buf[begin_i + 6]), 16)
                packet = input_buf[data_start_index:(data_start_index+data_len+2+3)]
                raw_data = packet[2:-3]
                print(f"!!!!! CALCULATING RECVING CHECKSUM ON LENGTH {data_len} FOR {raw_data}")
                calculated_checksum = functools.reduce(lambda a, b: a ^ b, raw_data)
                received_checksum = int(packet[-2:], 16)
                input_buf = b""
            except:
                #print(f"Failed to read checksum: {packet[-2:]}")
                print(f"Failed to read checksum")
                input_buf = b""
                cont_main_loop = True
                break
            if calculated_checksum != received_checksum:
                print(f"CHECKSUM: declared {received_checksum}, calculated {calculated_checksum}")
                input_buf = b""
                cont_main_loop = True
                break
            packet = base64.b64decode(raw_data.decode("ascii"))
            print("Received packet! Contents:")
            print(packet)
            handle_packet(packet)
        else:
            # this is an incomplete packet
            #old_seq = int(chr(input_buf[begin_i + 3]) + chr(input_buf[begin_i + 4]), 16)
            cont_main_loop = True

    if i_am_server or cont_main_loop or time.time() < wake_up_time:
        continue

    input_buf = b""

    # process net -> audio
    if i_am_server:
        sniff(filter=f"source host {origin_ip}", prn=send_net_to_audio_server, count=1)
    else:
        send_net_to_audio(tun.read(tun.mtu))
