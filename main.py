import os
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from pymongo import MongoClient
from typing import Optional, List
from dotenv import load_dotenv
from classifier import gpt_classification

# Load environment vars
load_dotenv()

# Initialize FastAPI and MongoDB client
app = FastAPI(
    title="Webpage Classification API",
    description="An API that classifies webpages into categories such as landing pages, live websites, or non-active domains. Includes API key management and rate limiting.",
    version="1.0.0"
)

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
    """Verify that the provided key matches the master key for privileged access."""
    if key != MASTER_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")


# Endpoint to generate API keys
@app.post("/api-keys/generate", response_model=APIKey, summary="Generate a new API key")
async def generate_api_key(rate_limit: Optional[int] = None, master_key: str = Depends(verify_master_key)):
    """
    Generate a new API key with an optional rate limit.

    - **rate_limit**: Optional. The maximum number of requests allowed for this key.
    - **master_key**: Required. The master key to authorize API key generation.

    ### Example Request
    ```python
    response = requests.post(
        "http://fastapi-classifier-1293371912.eu-north-1.elb.amazonaws.com:8001/generate",
        params={"key": "your_master_key"},
        json={"rate_limit": 100}
    )
    ```

    ### Example Response
    ```json
    {
      "api_key": "e4b27e89-08c3-4a68-9d3f-4adfe8c8b812",
      "created_at": "2024-11-05T10:12:45.472Z",
      "status": "active",
      "rate_limit": 100,
      "usage_count": 0
    }
    ```
    """
    new_key = str(uuid.uuid4())
    api_key_data = APIKey(api_key=new_key, created_at=datetime.utcnow(), rate_limit=rate_limit)
    api_keys_collection.insert_one(api_key_data.dict())
    return api_key_data


# Endpoint to revoke API keys
@app.delete("/api-keys/{api_key}", summary="Revoke an existing API key")
async def revoke_api_key(api_key: str, master_key: str = Depends(verify_master_key)):
    """
    Revoke an existing API key.

    - **api_key**: The API key to revoke.
    - **master_key**: Required. The master key to authorize revocation.

    ### Example Request
    ```python
    response = requests.delete(
    "http://fastapi-classifier-1293371912.eu-north-1.elb.amazonaws.com:8001/api-keys/{api_key}",
    params={"key": "your_master_key"})
    ```

    ### Example Response
    ```json
    {
      "message": "API key revoked successfully"
    }
    ```
    """
    result = api_keys_collection.update_one({"api_key": api_key, "status": "active"}, {"$set": {"status": "revoked"}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="API key not found or already revoked")
    return {"message": "API key revoked successfully"}


# Endpoint to list all API keys
@app.get("/api-keys", response_model=List[APIKey], summary="List all API keys")
async def list_api_keys(master_key: str = Depends(verify_master_key)):
    """
    List all API keys, including their statuses, rate limits, and usage counts.

    - **master_key**: Required. The master key to authorize listing.

    ### Example Request
    ```python
    response = requests.get("http://fastapi-classifier-1293371912.eu-north-1.elb.amazonaws.com:8001/api-keys", params={"key": "your_master_key"})
    ```

    ### Example Response
    ```json
    [
      {
        "api_key": "e4b27e89-08c3-4a68-9d3f-4adfe8c8b812",
        "created_at": "2024-11-05T10:12:45.472Z",
        "status": "active",
        "rate_limit": 100,
        "usage_count": 0
      },
      ...
    ]
    ```
    """
    api_keys = list(api_keys_collection.find({}, {"_id": 0}))
    return api_keys


# Endpoint to refresh an API key (reset usage_count to zero)
@app.put("/api-keys/{api_key}/refresh", response_model=APIKey, summary="Refresh an API key")
async def refresh_api_key(api_key: str, master_key: str = Depends(verify_master_key)):
    """
    Refresh an existing API key by resetting its usage count to zero.

    - **api_key**: The API key to refresh.
    - **master_key**: Required. The master key to authorize refreshing.

    ### Example Request
    ```python
    response = requests.put("http://fastapi-classifier-1293371912.eu-north-1.elb.amazonaws.com:8001/api-keys/{api_key}/refresh", params={"key": "your_master_key"})
    ```

    ### Example Response
    ```json
    {
      "api_key": "e4b27e89-08c3-4a68-9d3f-4adfe8c8b812",
      "created_at": "2024-11-05T10:12:45.472Z",
      "status": "active",
      "rate_limit": 100,
      "usage_count": 0
    }
    ```
    """
    existing_key = api_keys_collection.find_one({"api_key": api_key, "status": "active"})
    if not existing_key:
        raise HTTPException(status_code=404, detail="API key not found or inactive")

    updated_key_data = {
        "usage_count": 0,
        "created_at": datetime.utcnow()  # Optionally update the created_at timestamp to indicate refresh
    }

    api_keys_collection.update_one({"api_key": api_key}, {"$set": updated_key_data})
    existing_key.update(updated_key_data)
    return existing_key


# Classify URL Endpoint with API key and rate limiting
@app.get("/classify-url", summary="Classify a webpage URL")
async def classify_url(url: str, api_key: str):
    """
    Classify a webpage into categories (e.g., live website, landing page, non-active domain).

    - **url**: The URL to classify.
    - **api_key**: An active API key for authorization.

    ### Example Request
    ```python
    response = requests.get("http://fastapi-classifier-1293371912.eu-north-1.elb.amazonaws.com:8001/classify-url", params={"url": "example.com", "api_key": "your_api_key"})
    ```

    ### Example Response
    ```json
    {
      "url": "example.com",
      "classification": "live website",
      "source": "processed"
    }
    ```
    """
    api_key_data = api_keys_collection.find_one({"api_key": api_key, "status": "active"})
    if not api_key_data:
        raise HTTPException(status_code=403, detail="Invalid or inactive API key")

    if api_key_data["rate_limit"] is not None and api_key_data["usage_count"] >= api_key_data["rate_limit"]:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Check if the URL has already been processed
    existing_entry = classified_urls_collection.find_one({"url": url})
    if existing_entry:
        return {"url": url, "classification": existing_entry["classification"], "source": "cached"}

    # Process classification with retry logic
    result = await gpt_classification(url)

    # Save the result in MongoDB with a timestamp
    classified_urls_collection.insert_one({
        "url": url,
        "classification": result,
        "timestamp": datetime.utcnow()
    })

    # Update usage count
    api_keys_collection.update_one({"api_key": api_key}, {"$inc": {"usage_count": 1}})

    return {"url": url, "classification": result, "source": "processed"}


# New Poll Classification Endpoint
@app.get("/poll-classification", summary="Poll classification result for a URL")
async def poll_classification(url: str):
    """
    Poll the classification result of a previously classified URL.

    - **url**: The URL to poll for its classification result.

    ### Example Request
    ```python
    response = requests.get("http://fastapi-classifier-1293371912.eu-north-1.elb.amazonaws.com:8001/poll-classification", params={"url": "example.com"})
    ```

    ### Example Response
    ```json
    {
      "url": "example.com",
      "classification": "live website",
      "timestamp": "2024-11-05T10:12:45.472Z"
    }
    ```
    """
    existing_entry = classified_urls_collection.find_one({"url": url},
                                                         {"_id": 0, "url": 1, "classification": 1, "timestamp": 1})
    if not existing_entry:
        raise HTTPException(status_code=404, detail="Classification result not found for the given URL")

    return existing_entry


'''
docker build -t fastapi-classifier .  
docker tag fastapi-classifier:latest 531561883530.dkr.ecr.eu-north-1.amazonaws.com/fastapi-classifier:latest              
docker push 531561883530.dkr.ecr.eu-north-1.amazonaws.com/fastapi-classifier:latest  
'''