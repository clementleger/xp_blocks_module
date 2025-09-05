from enum import Enum
import sys
import time
import simplepyble

address = None

NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"

WRITE_CHAN_HEADER = "5a6b020008"

CHANNEL_COUNT = 6
MAX_POWER = 0xFF


class ChanId(Enum):
    CHAN_A = 0
    CHAN_B = 1
    CHAN_C = 2
    CHAN_D = 3
    CHAN_E = 4
    CHAN_F = 5


class ChanPair(Enum):
    CHAN_A_B = 0
    CHAN_C_D = 2
    CHAN_E_F = 4


def clamp(n, smallest, largest): return max(smallest, min(n, largest))


class Channel:
    def __init__(self, id: ChanId, chan_cmd_id: int):
        self.power = 0
        self.id = id
        self.chan_cmd_id = chan_cmd_id

    def set_power(self, power: int):
        power = clamp(power, 0, MAX_POWER)
        self.power = power

    def __str__(self):
        return self.id.value + ": " + self.power

    def __repr__(self):
        return self.id.name + ": " + str(self.power)

class Channels:
    def __init__(self):
        self.channels = list(map(lambda v: Channel(v[0], v[1]), [(ChanId.CHAN_A, 0x1), (ChanId.CHAN_B, 0x5), (
            ChanId.CHAN_C, 0x1), (ChanId.CHAN_D, 0x8), (ChanId.CHAN_E, 0x1), (ChanId.CHAN_F, 0x5)]))

    def set_power(self, chan_cmd_id: ChanId, power: int):
        self.channels[chan_cmd_id.value].set_power(power)

    def get_chan_pair_enable(self, pair: ChanPair) -> int:
        chan = 0
        id = pair.value
        if (self.channels[id].power):
            chan = chan | self.channels[id].chan_cmd_id
        if (self.channels[id + 1].power):
            chan = chan | self.channels[id + 1].chan_cmd_id

        return chan

    def get_chan_pair_power(self, pair: ChanPair) -> int:
        id = pair.value
        return max(self.channels[id].power, self.channels[id + 1].power)

    def to_cmd_bytes(self) -> bytearray:
        array = bytearray.fromhex(WRITE_CHAN_HEADER)

        # Second byte is channels power (only one value for both)
        array.append(self.get_chan_pair_enable(ChanPair.CHAN_A_B))
        array.append(self.get_chan_pair_power(ChanPair.CHAN_A_B))
        array.append(self.get_chan_pair_enable(ChanPair.CHAN_C_D))
        array.append(self.get_chan_pair_power(ChanPair.CHAN_C_D))
        array.append(0x1)

        array.append(self.get_chan_pair_enable(ChanPair.CHAN_E_F))
        array.append(self.channels[ChanId.CHAN_E.value].power)
        array.append(self.channels[ChanId.CHAN_F.value].power)

        csum = sum(b for b in array) % 256
        array.append(csum)

        return array


class XpModule:
    def __init__(self, peripheral, wserv, wchar):
        self.peripheral = peripheral
        self.wserv = wserv
        self.wchar = wchar
        self.channels = Channels()

    def write_channels(self):
        cmd_bytes = self.channels.to_cmd_bytes()
        cmd_bytes = bytes([byte for byte in cmd])
        self.peripheral.write_request(self.wserv.uuid(), self.wchar.uuid(), cmd_bytes)

def run_loop(xp_module: XpModule):
    while True:
        xp_module.channels.set_power(ChanId.CHAN_A, 0xFF)
        xp_module.channels.set_power(ChanId.CHAN_B, 0xFF)
        xp_module.write_channels()
        time.sleep(0.3)

if __name__ == "__main__":
    adapters = simplepyble.Adapter.get_adapters()

    if len(adapters) == 0:
        print("No adapters found")
    adapter = adapters[0]

    print(f"Selected adapter: {adapter.identifier()} [{adapter.address()}]")

    adapter.set_callback_on_scan_start(lambda: print("Scan started."))
    adapter.set_callback_on_scan_stop(lambda: print("Scan complete."))
    adapter.set_callback_on_scan_found(lambda peripheral: print(f"Found {peripheral.identifier()} [{peripheral.address()}]"))

    # Scan for 5 seconds
    adapter.scan_for(5000)
    peripherals = adapter.scan_get_results()

    xp_dev = None
    for i, peripheral in enumerate(peripherals):
        print(f"{i}: {peripheral.identifier()} [{peripheral.address()}]")

    for i, peripheral in enumerate(peripherals):
        name = peripheral.identifier()
        if name != None and name.startswith("JG_JMC"):
            print("Found XP Block device")
            xp_dev = peripheral

    if xp_dev == None:
        print("Failed to find XP block device")
        sys.exit(-1)

    print(f"Connecting to: {xp_dev.identifier()} [{xp_dev.address()}]")
    xp_dev.connect()

    services = xp_dev.services()
    wserv = None
    for service in services:
        if service.uuid() == SERVICE_UUID:
            wserv = service
            break
    
    if wserv == None:
        print("Failed to find XP block BLE service")
        sys.exit(-1)

    wchar = None
    for characteristic in wserv.characteristics():
            if characteristic.uuid() == WRITE_UUID:
                wchar = characteristic
                break
    
    if wchar == None:
        print("Failed to find XP block BLE write characteristic")
        sys.exit(-1)
 
    try:
        xp_module = XpModule(peripheral, wserv, wchar)  
        run_loop(xp_module)
    except KeyboardInterrupt:
        clear_channels = Channels()
        cmd = clear_channels.to_cmd_bytes()
        self.peripheral.write_request(self.wserv.uuid(), self.wchar.uuid(), cmd_bytes)
        peripheral.disconnect()
        sys.exit(0)

