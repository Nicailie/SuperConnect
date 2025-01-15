from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
import httpx
import asyncio
from datetime import datetime
from typing import List, Optional
import jwt
from fastapi.security import OAuth2PasswordBearer
import databases
import sqlalchemy


#Database setup
DatabaseURL = "sqlite:///./superconnect.db"
database = databases.Database(DatabaseURL)
metadata = sqlalchemy.MetaData()

#Models 
users = sqlalchemy.Table(
    "users",
    metadata, 
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key = True),
    sqlalchemy.Column("username", sqlalchemy.String, unique = True), 
    sqlalchemy.Column("hashedPassword", sqlalchemy.String), 
)

services = sqlalchemy.Table(
    "services", 
    metadata, 
    sqlalchemy.Column ("id", sqlalchemy.Integer, primary_key = True),
    sqlalchemy.Column ("userID", sqlalchemy.Integer),
    sqlalchemy.Column ("serviceName", sqlalchemy.String),
    sqlalchemy.Column ("accessToken", sqlalchemy.String),
)

#Pydantic models
class serviceConnect(BaseModel):
    serviceName: str
    accessToken: str

class User(BaseModel):
    userName: str
    password: str

class ServiceResponse(BaseModel):
    status: str
    data: dict

app = FastAPI(title = "Multi-Service Integration Hub")

@app.on_event("startup")
async def startup ():
    await database.connect()
    engine = sqlalchemy.create_engine(DatabaseURL)
    metadata.create_all(engine)

@app.on_event("shutdown")
async def shutdown ():
    await database.disconnect()

#Auth middleware
oauth2Scheme = OAuth2PasswordBearer(tokenUrl = "token")

async def get_current_user(token: str = Depends(oauth2Scheme)):
    try:
        payload = jwt.decode(token, "secretKey", algorithms = ["HS256"])
        userID = payload.get("sub")
        if userID is None:
            raise HTTPException( status_code = 401)
        return userID
    except jwt.JWTError:
        raise HTTPException(status_code = 401)

#Service integration handlers
async def handle_messaging_service(token: str, action: str, data: dict)-> dict:
    """Handle integration with messagings services (SMS, Email, etc.)"""
    #Simulate API call to messaging service
    await asyncio.sleep(1)
    return {"message_sent": True, "timestamp": str(datetime.now())}


async def handle_payment_service(token: str, action: str, data: dict)-> dict:
    """Handle integration with payment processing services"""
    #Simulate API call to messaging service
    await asyncio.sleep(1)
    return {"transaction_id": "tx_123", "status": "completed"}


async def handle_location_service(token: str, action: str, data: dict)-> dict:
    """Handle integration with location/mapping services"""
    #Simulate API call to messaging service
    await asyncio.sleep(1)
    return {"coordinates": {"lat": 37.7749, "lng": -122.4194}}

@app.post("/register")
async def register_user(user: User):
    query = users.insert().values(
        userName = user.userName, 
        hashedPassword = user.password  #in the production, hash the password
    )
    try: 
        userID = await database.execute(query)
        token = jwt.encode({"sub": userID}, "secret_key", algorithm="HS256")
        return {"accessToken": token, "tokenType": "bearer"}
    except Exception as e: 
        raise HTTPException(status_code = 400, detail = "Username already exists")
    
@app.post("connect-service")
async def connect_service(
    service: serviceConnect, 
    userID: int = Depends(get_current_user)
):
    query = services.insert().values(
        userID = userID, 
        serviceName = service.serviceName, 
        accessToken = service.accessToken
    )
    await database.execute(query)
    return {"status": "connected"}

@app.post("/execute/{service_name}/{action}")
async def execute_service_action(
    serviceName: str, 
    action: str, 
    data: dict, 
    userID: int = Depends(get_current_user)
):
    
    query = services.select().where(
        (services.c.userID == userID)&
        (services.c.serviceName == serviceName)
    )
    service = await database.fetch_one(query)
    if not service:
        raise HTTPException(
            status_code = 404, 
            detail = f"Service{serviceName} not connected"
        )
    
    #Execute service action
    handler = SERVICE_HANDLERS.get(serviceName)
    if not handler:
        raise HTTPException(
            status_code = 400, 
            detail = f"Service{serviceName} not connected"
        )
    
    result = await handler(service.accessToken, action, data)
    return ServiceResponse(status = "sucess", data = result)

@app.get("/services")
async def list_services(userID: int = Depends(get_current_user)):
    query = services.select().where(services.c.userID == userID)
    return await database.fetch_all(query)

@app.get("/")
async def root():
    return {
        "message": "Welcome to SuperConnect API",
        "version": "1.0",
        "endpoints": {
            "documentation": "/docs",
            "register": "/register",
            "connect_service": "/connect-service",
            "execute_service": "/execute/{service_name}/{action}",
            "list_services": "/services"
        }
    }

if __name__ == "__main__":
    import uvicorn 
    uvicorn.run(app, host = "127.0.0.1", port = 8000)