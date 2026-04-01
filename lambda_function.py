import json
import boto3
import random
import ast
from boto3.dynamodb.conditions import Key
from decimal import Decimal


dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("meal")

def convert_decimal(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    return obj

def calculate_calories(user):
    if user["gender"].lower() == "male":
        bmr = 10 * user["weight"] + 6.25 * user["height"] - 5 * user["age"] + 5
    else:
        bmr = 10 * user["weight"] + 6.25 * user["height"] - 5 * user["age"] - 161

    calories = bmr * 1.2

    if user["goal"] == "loss":
        calories -= 500
    elif user["goal"] == "gain":
        calories += 500

    return calories

def get_meal(meal_type, target_calories, goal):
    response = table.query(
        KeyConditionExpression=Key("meal_type").eq(meal_type)
    )

    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.query(
            KeyConditionExpression=Key("meal_type").eq(meal_type),
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))

    if not items:
        return {"message": f"No {meal_type} found"}

    score_col = {
        "loss": "score_loss",
        "gain": "score_gain",
        "maintain": "score_maintain"
    }.get(goal, "score_maintain")

    processed = []

    for item in items:
        calories = float(item.get("calories", 0))
        if calories == 0:
            continue

        calorie_diff = abs(calories - target_calories)
        score = float(item.get(score_col, 0))

        item["calorie_diff"] = calorie_diff
        item["goal_score"] = score

        processed.append(item)

    processed = sorted(
        processed,
        key=lambda x: (x["calorie_diff"], -x["goal_score"])
    )

    top_items = processed[:10]
    chosen = random.choice(top_items)

    try:
        chosen["ingredients"] = ast.literal_eval(chosen["ingredients"])
        chosen["steps"] = ast.literal_eval(chosen["steps"])
    except:
        pass

    return chosen

def lambda_handler(event, context):
    # Handle API Gateway invocation
    if "body" in event:
        body = json.loads(event["body"])
    else:
        # Direct invocation 
        body = event

    total_calories = calculate_calories(body)

    meal_split = {
        "breakfast": 0.25,
        "lunch": 0.35,
        "snack": 0.15,
        "dinner": 0.25
    }

    meal_plan = {}

    for meal_type, ratio in meal_split.items():
        calories = total_calories * ratio
        meal_plan[meal_type] = get_meal(meal_type, calories, body["goal"]) or {}

    response_body = {
        "daily_calories": round(total_calories),
        "goal": body["goal"],
        "meals": convert_decimal(meal_plan)
    }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response_body)
    }