from enum import Enum

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
        self.inverted = False
        self.chan_cmd_bit = chan_cmd_bit
        self.direction = Direction.FORWARD

    def set_inverted(self, inverted: bool):
        self.inverted = inverted
        self.set_direction(self.direction)

    def set_power(self, power: int):
        power = clamp(power, 0, MAX_POWER)
        self.power = power

    def set_direction(self, direction: Direction):
        if self.inverted:
            self.direction = Direction.FORWARD if direction == Direction.BACKWARD else Direction.BACKWARD
        else:
            self.direction = direction

    def __str__(self):
        return self.id.name + ": " + str(self.power)

    def __repr__(self):
        return self.id.name + ": " + str(self.power)

class Channels:
    def __init__(self):
        self.channels = list(map(lambda v: Channel(v[0], v[1]), [(ChanId.CHAN_A, 0x1), (ChanId.CHAN_B, 0x4), (
            ChanId.CHAN_C, 0x1), (ChanId.CHAN_D, 0x4), (ChanId.CHAN_E, 0x1), (ChanId.CHAN_F, 0x4)]))

    def set_inverted(self, chan_id: ChanId, inverted: bool):
        self.channels[chan_id.value].set_inverted(inverted)

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
            chan = chan | (self.channels[id + 1].chan_cmd_bit << self.channels[id + 1].direction.value)

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
    
    def set_inverted(self, chan_id: ChanId, inverted: bool):
        self.channels.set_inverted(chan_id, inverted)

    def set_power(self, chan_id: ChanId, power: int):
        self.channels.set_power(chan_id, power)

    def set_direction(self, chan_id: ChanId, direction: Direction):
        self.channels.set_direction(chan_id, direction)

    def write_channels(self):
        cmd_bytes = self.channels.to_cmd_bytes()
        cmd_bytes = bytes([byte for byte in cmd_bytes])
        self.peripheral.write_request(self.wserv.uuid(), self.wchar.uuid(), cmd_bytes)

    def clear(self):
        self.channels.clear()

    def reset(self):
        self.clear()
        self.write_channels()
