from enum import Enum
import random
import traceback
from xp_module import Direction, XpModule, ChanId, Channel
import argparse
import sys
import simplepyble
import yaml
import time

NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"

def get_millis():
    return time.time_ns() / 1_000_000

class ChanAction:
    def __init__(self, xp_module: XpModule, chan_id: ChanId, cfg):
        self.chan_id = chan_id
        self.cfg = cfg
        self.xp_module = xp_module

    def update(self):
        pass

class Static(ChanAction):
    def __init__(self, xp_module: XpModule, chan_id: ChanId, cfg):
        super().__init__(xp_module, chan_id, cfg)
        self.xp_module.set_power(self.chan_id, cfg["power"])
        if cfg.get("direction") != None:
            self.xp_module.set_direction(self.chan_id, Direction(cfg["direction"]))

class Flicker(ChanAction):
    def __init__(self, xp_module: XpModule, chan_id: ChanId, cfg):
        super().__init__(xp_module, chan_id, cfg)
        self.prng = random.randrange(0, 255)
        self.last_update = 0
        self.flicker_period = cfg.get("flicker_period", 100)
        self.on_off = cfg.get("on_off", False)
        self.off_threshold = cfg.get("off_threshold", 0)

    def update(self):
        if get_millis() - self.last_update < self.flicker_period:
            return

        self.last_update = get_millis()
        self.prng = (self.prng >> 1) ^ (-(self.prng & 1) & 0xB8)
        self.prng &= 0xFF

        if self.on_off:
            if self.prng > 128:
                self.xp_module.set_power(self.chan_id, 255)
            else:
                self.xp_module.set_power(self.chan_id, 0)
        else:
            value = self.prng
            if value < self.off_threshold:
                value = 0
            self.xp_module.set_power(self.chan_id, value)

class Scenario:
    def __init__(self, xp_module: XpModule, file: str):
        with open(file, "r") as file:
            self.config = yaml.safe_load(file)
        
        for chan in self.config["map"].values():
            chan_id = ChanId(chan["id"])
            if chan.get("inverted") != None:
                xp_module.set_inverted(chan_id, chan["inverted"])
    
    def get_chan_id_for_name(self, name: str) -> ChanId:
        chan = self.config["map"][name]["id"]
        return ChanId(chan)

class Step:
    def __init__(self, cfg, scenario: Scenario, xp_module: XpModule):
        self.cfg = cfg
        self.name = cfg.get("name", "Unnamed Step")
        self.xp_module = xp_module
        self.xp_module.clear()
        self.actions = []
        self.duration = cfg["duration"] * 1000  # Convert to milliseconds
        if not "channels" in self.cfg:
            return

        for chan_cfg in self.cfg["channels"]:
            for name, cfg in chan_cfg.items():
                chan_id = scenario.get_chan_id_for_name(name)
                match cfg["type"]:
                    case "static":
                        self.actions.append(Static(xp_module, chan_id, cfg))
                    case "flicker":
                        self.actions.append(Flicker(xp_module, chan_id, cfg))

    def execute(self):
        start_time = get_millis()
        last_refresh = 0
        print(f"Executing step {self.name} for duration {self.duration} ms")
        while (get_millis() < start_time + self.duration):
            if (get_millis() - last_refresh) < args.refresh_rate:
                continue

            last_refresh = get_millis()
            for action in self.actions:
                action.update()

            self.xp_module.write_channels()

def run_scenario(xp_module: XpModule, args):
    scenario = Scenario(xp_module, args.scenario_file)
    print(f"Executing scenario {scenario.config['scenario']['name']} for {args.duration} minutes")
    start_time = time.time()
    while time.time() < start_time + (args.duration * 60):
        step_count = len(scenario.config["scenario"]["steps"])
        next_step = random.randrange(0, step_count)
        step = scenario.config["scenario"]["steps"][next_step]
        Step(step, scenario, xp_module).execute()

def list_adapters():
    adapters = simplepyble.Adapter.get_adapters()
    for i, adapter in enumerate(adapters):
        try:
            print(f"{i}: {adapter.identifier()} [{adapter.address()}]")
        except Exception as e:
            pass
    
    return adapters

def connect_device(xp_dev, args):
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
        run_scenario(xp_module, args)
    except KeyboardInterrupt:
        print("Exiting...")
    except:
        traceback.print_exc()

    xp_module.reset()
    xp_dev.disconnect()


if __name__ == "__main__":

    # Instantiate the parser
    parser = argparse.ArgumentParser(description='XP module block app')
    parser.add_argument('-a', '--adapter', type=int, default=0, help='Index of the BLE adapter to use')
    parser.add_argument('-A', '--address', type=str, help='Address of the XP block device to connect to')
    parser.add_argument('-N', '--name', type=str, help='Name of the XP block device to connect to') 
    parser.add_argument('-l', '--list-adapters', action='store_true', help='List available BLE adapters and exit')
    parser.add_argument('-L', '--list-devices', action='store_true', help='List available BLE devices and exit')
    parser.add_argument('-f', '--scenario-file', type=str, help='File path to scenario YAML file to execute')
    parser.add_argument('-r', '--refresh-rate', type=int, help='Refresh rate in milliseconds', default=20)
    parser.add_argument('-d', '--duration', type=int, help='Run duration in minutes', default=60)

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

    if not args.scenario_file:
        print("Please specify a scenario file to execute")
        sys.exit(-1)

    if not args.name and not args.address:
        print("Please specify either a device name or address to connect to")
        sys.exit(-1)

    xp_dev = None
    if args.name:
        xp_dev = next(dev for dev in peripherals if dev.identifier() == args.name)
        if xp_dev == None:
            print("XP block device not found")
            sys.exit(-1)
    elif args.address:
        xp_dev = next(dev for dev in peripherals if dev.address() == args.address)
        if xp_dev == None:
            print("XP block device not found")
            sys.exit(-1)
    
    name = xp_dev.identifier()
    if name == None or not name.startswith("JG_JMC"):
        print("Invalid XP block device")
        sys.exit(-1)

    connect_device(xp_dev, args)

    sys.exit(0)