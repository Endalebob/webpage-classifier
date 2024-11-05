import os
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from pymongo import MongoClient
from typing import Optional, List
from dotenv import load_dotenv
from classifier import gpt_classification

# Load environment variables
load_dotenv()

# Initialize FastAPI and MongoDB client
app = FastAPI()
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["webpage_classification_db"]
api_keys_collection = db["api_keys"]
classified_urls_collection = db["classified_urls"]

# Master key for API key management
MASTER_KEY = os.getenv("MASTER_KEY")


# API Key Data Model
class APIKey(BaseModel):
    api_key: str
    created_at: datetime
    status: str = "active"
    rate_limit: Optional[int] = None
    usage_count: int = 0


# Dependency to check master key
def verify_master_key(key: str):
    if key != MASTER_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")


# Endpoint to generate API keys
@app.post("/api-keys/generate", response_model=APIKey)
async def generate_api_key(rate_limit: Optional[int] = None, master_key: str = Depends(verify_master_key)):
    new_key = str(uuid.uuid4())
    api_key_data = APIKey(api_key=new_key, created_at=datetime.utcnow(), rate_limit=rate_limit)
    api_keys_collection.insert_one(api_key_data.dict())
    return api_key_data


# Endpoint to revoke API keys
@app.delete("/api-keys/{api_key}")
async def revoke_api_key(api_key: str, master_key: str = Depends(verify_master_key)):
    result = api_keys_collection.update_one({"api_key": api_key, "status": "active"}, {"$set": {"status": "revoked"}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="API key not found or already revoked")
    return {"message": "API key revoked successfully"}


# Endpoint to list all API keys
@app.get("/api-keys", response_model=List[APIKey])
async def list_api_keys(master_key: str = Depends(verify_master_key)):
    api_keys = list(api_keys_collection.find({}, {"_id": 0}))
    return api_keys


# Endpoint to refresh an API key (reset usage_count to zero)
@app.put("/api-keys/{api_key}/refresh", response_model=APIKey)
async def refresh_api_key(api_key: str, master_key: str = Depends(verify_master_key)):
    # Find the existing API key
    existing_key = api_keys_collection.find_one({"api_key": api_key, "status": "active"})
    if not existing_key:
        raise HTTPException(status_code=404, detail="API key not found or inactive")

    # Reset usage_count to zero and update the timestamp
    updated_key_data = {
        "usage_count": 0,
        "created_at": datetime.utcnow()  # Optionally update the created_at timestamp to indicate refresh
    }

    # Update the existing key in the database
    api_keys_collection.update_one({"api_key": api_key}, {"$set": updated_key_data})

    # Return the updated key data
    existing_key.update(updated_key_data)  # Update the in-memory data with new values
    return existing_key


# Classify URL Endpoint with API key and rate limiting
@app.get("/classify-url")
async def classify_url(url: str, api_key: str):
    # Check API key validity
    api_key_data = api_keys_collection.find_one({"api_key": api_key, "status": "active"})
    if not api_key_data:
        raise HTTPException(status_code=403, detail="Invalid or inactive API key")

    # Enforce rate limit
    if api_key_data["rate_limit"] is not None and api_key_data["usage_count"] >= api_key_data["rate_limit"]:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Check if the URL has already been processed
    existing_entry = classified_urls_collection.find_one({"url": url})
    if existing_entry:
        return {"url": url, "classification": existing_entry["classification"], "source": "cached"}

    # Process classification
    try:
        result = await gpt_classification(url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during classification: {str(e)}")

    # Save the result in MongoDB with a timestamp
    classified_urls_collection.insert_one({
        "url": url,
        "classification": result,
        "timestamp": datetime.utcnow()
    })

    # Update usage count
    api_keys_collection.update_one({"api_key": api_key}, {"$inc": {"usage_count": 1}})

    return {"url": url, "classification": result, "source": "processed"}

'''
docker build -t fastapi-classifier .  
docker tag fastapi-classifier:latest 531561883530.dkr.ecr.eu-north-1.amazonaws.com/fastapi-classifier:latest              
docker push 531561883530.dkr.ecr.eu-north-1.amazonaws.com/fastapi-classifier:latest  
'''