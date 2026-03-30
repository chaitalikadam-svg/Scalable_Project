import boto3
import random
import os
import ast
import uuid
import json
from fastapi import FastAPI
from pydantic import BaseModel
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from fastapi import HTTPException
from boto3.dynamodb.conditions import Attr
import bcrypt
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
import requests
from datetime import datetime
from fastapi import FastAPI, Request, Depends

app = FastAPI(title="Meal Planner API")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY")
)

# DynamoDB
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
users_table = dynamodb.Table("user")

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("meal")

# -------------------------------
# Input Model
# -------------------------------
class UserInput(BaseModel):
    height: float
    weight: float
    age: int
    gender: str
    goal: str   # loss / gain / maintain

class LoginInput(BaseModel):
    email: str
    password: str

class SignupInput(BaseModel):
    email: str
    password: str
# -------------------------------
# Calorie Calculation
# -------------------------------

def get_bmi_from_api(height, weight):

    url = "https://bmi-calculator-api-apiverve.p.rapidapi.com/v1/bmicalculator"

    headers = {
        "x-rapidapi-key": "71293b1671msh055c268f75bfe27p100c45jsnd66db148faa5",
        "x-rapidapi-host": "bmi-calculator-api-apiverve.p.rapidapi.com",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    params = {
        "weight": str(weight),
        "height": str(height),
        "unit": "metric"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        response.raise_for_status()

        data = response.json()
        
        print("FULL API RESPONSE:", data)

        # 🔥 adapt response (important)
        bmi = float(data.get("data", {}).get("bmi", 0))
        category = data.get("data", {}).get("risk", "unknown")
        summary = data.get("data", {}).get("summary", "unknown")

        return {
        "bmi": bmi,
        "category": category,
        "summary": summary,
    }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BMI API failed: {str(e)}")

def get_current_user(request: Request):
    email = request.session.get("user")

    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    return {"email_id": email}
# -------------------------------
# MAIN API
# -------------------------------
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.responses import HTMLResponse
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})
    
@app.post("/signup")
def signup(data: SignupInput):

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    users_table = dynamodb.Table("user")   # ✅ new table

    # ✅ direct lookup (no scan)
    response = users_table.get_item(
        Key={"email_id": data.email}
    )

    if "Item" in response:
        raise HTTPException(status_code=400, detail="User already exists")

    import bcrypt
    hashed_password = bcrypt.hashpw(
        data.password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    users_table.put_item(
        Item={
            "email_id": data.email,   # ✅ only key needed
            "password": hashed_password
        }
    )
    return {"message": "Signup successful"}

@app.post("/login")
def login(data: LoginInput, request: Request):

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    users_table = dynamodb.Table("user")   

    response = users_table.get_item(
        Key={"email_id": data.email}
    )

    user = response.get("Item")

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    import bcrypt
    if not bcrypt.checkpw(
        data.password.encode('utf-8'),
        user["password"].encode('utf-8')
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # ✅ store session
    request.session["user"] = data.email

    return {"message": "Login successful"}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/mealplan")
def get_meal_plan(user: UserInput):

    # Convert Pydantic model to dict
    payload = {
        "height": user.height,
        "weight": user.weight,
        "age": user.age,
        "gender": user.gender,
        "goal": user.goal
    }

    # Call your API Gateway endpoint
    api_url = "https://z67upt1czc.execute-api.us-east-1.amazonaws.com/mealplan"

    response = requests.post(api_url, json=payload)

    # Raise error if API Gateway fails
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Meal API failed")

    return response.json()

@app.get("/get-profile")
def get_profile(request: Request):

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    users_table = dynamodb.Table("user")

    email = request.session.get("user")

    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    response = users_table.get_item(
        Key={"email_id": email}
    )

    user = response.get("Item")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Convert Decimal to float for JSON serialization
    return {
        "email_id": user.get("email_id"),
        "name": user.get("name", ""),
        "height": float(user.get("height", 0)),
        "weight": float(user.get("weight", 0)),
        "age": int(user.get("age", 0)),
        "gender": user.get("gender", ""),
        "goal": user.get("goal", "")
    }

@app.post("/save-profile")
def save_profile(request: Request, data: dict):

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    users_table = dynamodb.Table("user")

    email = request.session.get("user")
    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    # Timestamp for history entries
    timestamp = datetime.utcnow().isoformat()

    # Prepare history items
    height_item = {
        "value": Decimal(str(data["height"])),
        "timestamp": timestamp
    }
    weight_item = {
        "value": Decimal(str(data["weight"])),
        "timestamp": timestamp
    }
    age_item = {
        "value": int(data["age"]),
        "timestamp": timestamp
    }

    # Update current values + append history
    users_table.update_item(
        Key={"email_id": email},
        UpdateExpression="""
            SET #n = :name,
                height = :height,
                weight = :weight,
                age = :age,
                gender = :gender,
                height_history = list_append(if_not_exists(height_history, :empty), :h_item),
                weight_history = list_append(if_not_exists(weight_history, :empty), :w_item),
                age_history = list_append(if_not_exists(age_history, :empty), :a_item)
        """,
        ExpressionAttributeNames={
            "#n": "name"
        },
        ExpressionAttributeValues={
            ":name": data["name"],
            ":height": Decimal(str(data["height"])),
            ":weight": Decimal(str(data["weight"])),
            ":age": int(data["age"]),
            ":gender": data["gender"],
            ":empty": [],
            ":h_item": [height_item],
            ":w_item": [weight_item],
            ":a_item": [age_item]
        }
    )

    return {
        "message": "Profile saved with history",
        "timestamp": timestamp
    }
    
@app.post("/get-bmi")
def get_bmi(request: Request):
    
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    users_table = dynamodb.Table("user")  

    email = request.session.get("user")

    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    user = users_table.get_item(
        Key={"email_id": email}
    ).get("Item")

    if not user:
        raise HTTPException(status_code=404, detail="Profile not found")

    height = float(user["height"])
    weight = float(user["weight"])

    bmi_data = get_bmi_from_api(height, weight)

    bmi = bmi_data["bmi"]

    # 🔥 goal logic
    if bmi < 18.5:
        goal = "gain"
    elif bmi < 25:
        goal = "maintain"
    else:
        goal = "loss"

    # 🔥 update DB
    users_table.update_item(
        Key={"email_id": email},
        UpdateExpression="SET goal = :g",
        ExpressionAttributeValues={":g": goal}
    )

    return {
    "bmi": bmi,
    "category": bmi_data["category"],
    "summary": bmi_data["summary"],  
    "goal": goal
}
    
@app.get("/trend-data")
def trend_data(request: Request, current_user: dict = Depends(get_current_user)):
    s3 = boto3.client("s3")
    bucket = "mealplanner-trends"

    prefix = f"weight_trends/{current_user['email_id']}/"

    # List only this user's trend files
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    if "Contents" not in resp:
        return []

    records = []

    # Read all JSON files for this user
    for obj in resp["Contents"]:
        file = s3.get_object(Bucket=bucket, Key=obj["Key"])
        content = file["Body"].read().decode("utf-8")

        for line in content.splitlines():
            records.append(json.loads(line))

    # Sort by timestamp
    records = sorted(records, key=lambda x: x["timestamp"])

    return records
    
@app.post("/run-trend-job")
def run_trend_job(request: Request, current_user: dict = Depends(get_current_user)):
    glue = boto3.client("glue", region_name="us-east-1")

    try:
        response = glue.start_job_run(
            JobName="weighttrend",
            Arguments={"--USER_EMAIL": current_user["email_id"]}
        )
        return {"message": "Trend job started", "runId": response["JobRunId"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))