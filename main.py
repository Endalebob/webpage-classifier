from fastapi import FastAPI, HTTPException
from classifier import gpt_classification

app = FastAPI()

@app.get("/classify-url")
async def classify_url(url: str):
    try:
        # Await the asynchronous classification function
        result = await gpt_classification(url)
        return {"url": url, "classification": result}
    except Exception as e:
        # Catch any exception and raise an HTTP 500 error with a message
        raise HTTPException(status_code=500, detail=f"An error occurred during classification: {str(e)}")



'''
docker build -t fastapi-classifier .  
docker tag fastapi-classifier:latest 531561883530.dkr.ecr.eu-north-1.amazonaws.com/fastapi-classifier:latest              
docker push 531561883530.dkr.ecr.eu-north-1.amazonaws.com/fastapi-classifier:latest  
'''