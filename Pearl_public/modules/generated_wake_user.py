import asyncio
async def wake_up_user(time: str):
    await asyncio.sleep(1)
    print(f"Waking up user at {time}")
