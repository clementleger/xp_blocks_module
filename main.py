from xp_module import XpModule, ChanId
import argparse
import sys
import simplepyble
import yaml

address = None

NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"

class Scenario:
    def __init__(self, file: str):
        with open(file, "r") as file:
            self.config = yaml.safe_load(file)
    
    def get_channel_for_name(self, name: str) -> ChanId:
        chan = self.config["map"][name]["id"]
        return ChanId(chan)

def execute_scenario(xp_module: XpModule, scenario: Scenario):
    for step in scenario.config["scenario"]["steps"]:
        duration = step["duration"]
        print(f"Executing step for {duration} seconds")
        for chan_cfg in step["channels"]:
            for name, cfg in chan_cfg.items():
                chan_id = scenario.get_channel_for_name(name)
                power = cfg.get("channel", 0)
                print(f" - Setting channel {name} (id={chan_id}) to power {power}")
                xp_module.channels.set_power(chan_id, power)
        xp_module.write_channels()
        xp_module.wait(duration)

def run_loop(xp_module: XpModule):
    while True:
        xp_module.channels.set_power(ChanId.CHAN_A, 255)
        xp_module.channels.set_power(ChanId.CHAN_B, 255)
        xp_module.write_channels()

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
    parser.add_argument('-N', '--name', type=str, help='Name of the XP block device to connect to') 
    parser.add_argument('-l', '--list-adapters', action='store_true', help='List available BLE adapters and exit')
    parser.add_argument('-L', '--list-devices', action='store_true', help='List available BLE devices and exit')
    parser.add_argument('-f', '--scenario-file', type=str, help='File path to scenario YAML file to execute')

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

