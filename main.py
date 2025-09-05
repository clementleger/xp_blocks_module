import asyncio
from enum import Enum
from bleak import BleakClient, BleakScanner

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
    def __init__(self, client, device, write_charact):
        self.client = client
        self.device = device
        self.write_charact = write_charact
        self.channels = Channels()

async def handle_device(client, write_charact):
    channels = Channels()

    power = 0
    while(True):
        power += 50
        if power >= 256:
            power = 10

        channels.set_power(ChanId.CHAN_A, power)
        channels.set_power(ChanId.CHAN_B, power)
        cmd = channels.to_cmd_bytes()
        resp = await client.write_gatt_char(write_charact, cmd, True)
        await asyncio.sleep(0.01)

async def init_dev(device):
    async with BleakClient(device) as client:
        for service in client.services:
            if service.uuid == SERVICE_UUID:
                for charact in service.characteristics:
                    if charact.uuid == WRITE_UUID:
                        await handle_device(client, charact)


async def main():
    devices = await BleakScanner.discover()
    for d in devices:
        if d.name != None and d.name.startswith("JG_JMC"):
            print("Found xp device " + str(d))
            await init_dev(d)
            return

    print("No XP blocks module available")

asyncio.run(main())
