import boto3
import pandas as pd
from decimal import Decimal

# 🔹 Config
TABLE_NAME = "recipes"
CSV_FILE = "recipes_sampled.csv"

# 🔹 Init DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

# 🔹 Load CSV
df = pd.read_csv(CSV_FILE)
df.columns = df.columns.str.strip()

print("Total rows:", len(df))


# 🔥 Convert safely (important for DynamoDB)
def to_decimal(value):
    try:
        return Decimal(str(value))
    except:
        return Decimal("0")


def convert_row(row):
    return {
        "recipe_id": str(row["recipe_id"]),  # ✅ use existing ID

        "name": str(row.get("name", "")),
        "meal_type": str(row.get("meal_type", "")),

        "calories": to_decimal(row.get("calories", 0)),
        "protein": to_decimal(row.get("protein", 0)),
        "fat": to_decimal(row.get("fat", 0)),

        "protein_per_100cal": to_decimal(row.get("protein_per_100cal", 0)),
        "fat_per_100cal": to_decimal(row.get("fat_per_100cal", 0)),

        "score_loss": to_decimal(row.get("score_loss", 0)),
        "score_gain": to_decimal(row.get("score_gain", 0)),
        "score_maintain": to_decimal(row.get("score_maintain", 0)),

        "servings": str(row.get("servings", "")),
        "serving_size": str(row.get("serving_size", "")),

        "ingredients": str(row.get("ingredients", "")),
        "ingredients_raw_str": str(row.get("ingredients_raw_str", "")),
        "steps": str(row.get("steps", "")),
    }


# 🔥 Batch upload (fast & efficient)
with table.batch_writer() as batch:
    for _, row in df.iterrows():
        item = convert_row(row)
        batch.put_item(Item=item)

print("✅ Data uploaded successfully to DynamoDB!")