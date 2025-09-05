import asyncio
from bleak import BleakClient, BleakScanner

address = None

NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"

async def connect(address):
    async with BleakClient(address) as client:
        for service in client.services:
             print(service)
             if service.uuid == SERVICE_UUID:
                for charact in service.characteristics:
                     print(charact)
                  
        #      dataawait data = client.read_gatt_char(service.uuid)
        #      print(data)


async def main():
    devices = await BleakScanner.discover()
    for d in devices:
        print(d)
        if d.name != None and d.name.startswith("JG_JMC"):
                await connect(d.address)
                break

asyncio.run(main())
