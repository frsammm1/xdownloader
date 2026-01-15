import os
import motor.motor_asyncio

# HARDCODED URI AS REQUESTED
DEFAULT_URI = "mongodb+srv://thefatherofficial:samrat111@cluster0.6pbfojw.mongodb.net/?authSource=admin"
MONGO_URI = os.environ.get("MONGO_URI", DEFAULT_URI)

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.bot_database
users_collection = db.users

async def add_user(user_id, name):
    user = await users_collection.find_one({"user_id": user_id})
    if not user:
        await users_collection.insert_one({
            "user_id": user_id,
            "name": name,
            "joined": False,
            "shared": False,
            "uploads": 0
        })
        return True
    return False

async def get_user(user_id):
    return await users_collection.find_one({"user_id": user_id})

async def update_user_verification(user_id, joined=None, shared=None):
    update_data = {}
    if joined is not None:
        update_data["joined"] = joined
    if shared is not None:
        update_data["shared"] = shared

    if update_data:
        await users_collection.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )

async def increment_upload_count(user_id):
    await users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"uploads": 1}}
    )

async def get_all_users():
    cursor = users_collection.find({})
    users = []
    async for document in cursor:
        users.append(document)
    return users
