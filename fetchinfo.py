import json


# Load credits from JSON
def load_credits():
    try:
        with open('credits.json', 'r') as f:
            data = f.read()
            if data:
                return json.loads(data)
            else:
                return {}  # Return an empty dictionary if the file is empty
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Save credits to JSON
def save_credits(credits):
    with open('credits.json', 'w') as f:
        json.dump(credits, f)
