# routes.py
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
import asyncio
from datetime import datetime

# Initialize data store
bms_store = BMSDataStore()

# Load register map
register_map = ModbusMap.from_json("modbus_map.json")

async def update_bms_data():
    while True:
        try:
            # Update each unit
            units = [1,2]  # You'll need to get your actual unit IDs
            for unit_id in units:
                # Get updated values
                values = await read_holding_registers(register_map, slave_id=unit_id)
                await bms_store.update_unit_data(unit_id, values)
            
            # Wait before next update
            await asyncio.sleep(30)  # 30 second update interval
        except Exception as e:
            print(f"Error updating BMS data: {e}")
            await asyncio.sleep(5)  # Wait before retry on error

@app.on_event("startup")
async def startup_event():
    # Start the background task
    asyncio.create_task(update_bms_data())

@app.get("/bms")
async def bms(request: Request):
    # Get latest data
    bms_data = await bms_store.get_all_data()
    
    return templates.TemplateResponse(
        "bms.html",
        {
            "request": request,
            "bms_data": bms_data,
            "register_map": register_map,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )
