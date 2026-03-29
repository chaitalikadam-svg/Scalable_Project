import pandas as pd

# 🔹 Load your full dataset
df = pd.read_csv("recipes_cleaned_glue.csv")

# Clean column names
df.columns = df.columns.str.strip()

print("Total rows before:", len(df))

# 🔹 Ensure lowercase consistency
df["meal_type"] = df["meal_type"].str.lower()

# 🔹 Sampling function
def sample_meals(df, meal_type, n):
    subset = df[df["meal_type"] == meal_type]
    
    if len(subset) < n:
        print(f"⚠️ Only {len(subset)} available for {meal_type}")
        return subset
    
    return subset.sample(n=n, random_state=42)

# 🔹 Sample each category
breakfast_df = sample_meals(df, "breakfast", 35)
snack_df     = sample_meals(df, "snack", 35)
lunch_df     = sample_meals(df, "lunch", 50)
dinner_df    = sample_meals(df, "dinner", 50)

# 🔹 Combine all
final_df = pd.concat([
    breakfast_df,
    snack_df,
    lunch_df,
    dinner_df
])

# 🔹 Shuffle final dataset
final_df = final_df.sample(frac=1, random_state=42)

print("Total rows after:", len(final_df))

# 🔹 Save new file
final_df.to_csv("recipes_sampled.csv", index=False)

print("✅ Sampled dataset saved as recipes_sampled.csv")