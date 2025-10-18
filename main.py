from enum import Enum
import argparse
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

class Direction(Enum):
    FORWARD = 0
    BACKWARD = 1

def clamp(n, smallest, largest): return max(smallest, min(n, largest))


class Channel:
    def __init__(self, id: ChanId, chan_cmd_bit: int):
        self.power = 0
        self.id = id
        self.chan_cmd_bit = chan_cmd_bit
        self.direction = Direction.FORWARD

    def set_power(self, power: int):
        power = clamp(power, 0, MAX_POWER)
        self.power = power

    def set_direction(self, direction: Direction):
        self.direction = direction

    def __str__(self):
        return self.id.value + ": " + self.power

    def __repr__(self):
        return self.id.name + ": " + str(self.power)

class Channels:
    def __init__(self):
        self.channels = list(map(lambda v: Channel(v[0], v[1]), [(ChanId.CHAN_A, 0x1), (ChanId.CHAN_B, 0x4), (
            ChanId.CHAN_C, 0x1), (ChanId.CHAN_D, 0x4), (ChanId.CHAN_E, 0x1), (ChanId.CHAN_F, 0x4)]))

    def set_power(self, chan_id: ChanId, power: int):
        self.channels[chan_id.value].set_power(power)

    def set_direction(self, chan_id: ChanId, direction: Direction):
        self.channels[chan_id.value].set_direction(direction)

    def clear(self):
        for channel in self.channels:
            channel.set_power(0)

    def get_chan_pair_enable(self, pair: ChanPair) -> int:
        chan = 0
        id = pair.value
        if (self.channels[id].power):
            chan = chan | (self.channels[id].chan_cmd_bit << self.channels[id].direction.value)
        if (self.channels[id + 1].power):
            chan = chan | (self.channels[id + 1].chan_cmd_bit << self.channels[id].direction.value)

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
        cmd_bytes = bytes([byte for byte in cmd_bytes])
        self.peripheral.write_request(self.wserv.uuid(), self.wchar.uuid(), cmd_bytes)

    def reset(self):
        self.channels.clear()
        self.write_channels()

    def set_1_sec(self, channel: Channel):
        self.channels.set_direction(channel, Direction.FORWARD)
        self.channels.set_power(channel, 0xFF)
        self.write_channels()
        time.sleep(1)
        self.channels.set_power(channel, 0x0)
        self.write_channels()
        time.sleep(1)
        self.channels.set_direction(channel, Direction.BACKWARD)
        self.channels.set_power(channel, 0xFF)
        self.write_channels()
        time.sleep(1)
        self.channels.set_power(channel, 0x0)
        self.write_channels()
        time.sleep(1)

def run_loop(xp_module: XpModule):
    while True:
        xp_module.set_1_sec(ChanId.CHAN_A)

def list_adapters():
    adapters = simplepyble.Adapter.get_adapters()
    for i, adapter in enumerate(adapters):
        try:
            print(f"{i}: {adapter.identifier()} [{adapter.address()}]")
        except Exception as e:
            pass
    
    return adapters

if __name__ == "__main__":

    # Instantiate the parser
    parser = argparse.ArgumentParser(description='XP module block app')
    parser.add_argument('-a', '--adapter', type=int, default=0, help='Index of the BLE adapter to use')
    parser.add_argument('-A', '--address', type=str, help='Address of the XP block device to connect to') 
    parser.add_argument('-l', '--list-adapters', action='store_true', help='List available BLE adapters and exit')
    parser.add_argument('-L', '--list-devices', action='store_true', help='List available BLE devices and exit')

    args = parser.parse_args()

    adapters = list_adapters()
    if args.list_adapters:
        sys.exit(0)

    if args.adapter < 0 or args.adapter >= len(adapters):
        print("Invalid adapter index")
        sys.exit(-1)

    adapter = adapters[args.adapter]
    adapter.set_callback_on_scan_start(lambda: print("Scan started."))
    adapter.set_callback_on_scan_stop(lambda: print("Scan complete."))

    # Scan for 5 seconds
    adapter.scan_for(5000)
    peripherals = adapter.scan_get_results()

    xp_dev = None
    for i, peripheral in enumerate(peripherals):
        if len(peripheral.identifier()) != 0:
            print(f"{i}: {peripheral.identifier()} [{peripheral.address()}]")

    if args.list_devices:
        sys.exit(0)

    xp_dev = next(dev for dev in peripherals if dev.address() == args.address) if args.address else None
    if xp_dev == None:
        print("XP block device not found")
        sys.exit(-1)
    
    name = xp_dev.identifier()
    if name == None or not name.startswith("JG_JMC"):
        print("Invalid XP block device")
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
 
    xp_module = XpModule(xp_dev, wserv, wchar) 
    try: 
        run_loop(xp_module)
    except:
        xp_module.reset()
        print("Exiting...")
        xp_dev.disconnect()
        sys.exit(0)

