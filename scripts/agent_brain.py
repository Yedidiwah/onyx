import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# טעינת המפתחות
MCP_TOKEN = os.getenv("VILLIERS_MCP_TOKEN")
MCP_URL = "https://mcp.villiers.ai/mcp"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# פונקציה לתקשורת עם השרת של Villiers
def get_jet_estimate_from_villiers(origin, destination, date, passengers=1):
    print(f"\n[מערכת] ה-AI החליט לפנות ל-Villiers עבור המסלול: {origin} -> {destination}...")
    headers = {
        "Authorization": f"Bearer {MCP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_jet_estimate",
            "arguments": {
                "origin": origin,
                "destination": destination,
                "date": date,
                "passengers": passengers
            }
        }
    }
    try:
        response = requests.post(MCP_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# הפונקציה הראשית שמפעילה את הסוכן
def run_onyx_agent(user_message):
    print(f"\nלקוח: {user_message}")
    
    # הגדרת סוכן ה-AI והכלים שלו
    system_prompt = """
    You are the luxury private jet concierge for ONYX (flywithonyx.com).
    Your goal is to provide exceptional, high-end customer service.
    When a user asks for a flight, use the get_jet_estimate tool to find the price.
    Always reply in a professional, luxurious tone. If the user writes in Hebrew, reply in Hebrew.
    """

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_jet_estimate",
                "description": "Get indicative pricing for a private jet charter.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string", "description": "3-letter IATA airport code for origin (e.g., LHR)"},
                        "destination": {"type": "string", "description": "3-letter IATA airport code for destination (e.g., NCE)"},
                        "date": {"type": "string", "description": "Date of flight in YYYY-MM-DD format"},
                        "passengers": {"type": "integer", "description": "Number of passengers"}
                    },
                    "required": ["origin", "destination", "date"]
                }
            }
        }
    ]

    # שלב 1: שולחים את הבקשה ל-OpenAI
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        tools=tools,
        tool_choice="auto"
    )

    response_message = response.choices[0].message

    # שלב 2: ה-AI בודק אם הוא צריך להשתמש בכלי (Villiers API)
    if response_message.tool_calls:
        tool_call = response_message.tool_calls[0]
        arguments = json.loads(tool_call.function.arguments)
        
        # מפעילים את הפונקציה האמיתית מול Villiers
        function_response = get_jet_estimate_from_villiers(
            origin=arguments.get('origin'),
            destination=arguments.get('destination'),
            date=arguments.get('date'),
            passengers=arguments.get('passengers', 1)
        )
        
        # שלב 3: מחזירים את התשובה מ-Villiers ל-OpenAI כדי שינסח תשובה ללקוח
        final_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
                response_message,
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": json.dumps(function_response)
                }
            ]
        )
        print("\nסוכן ONYX:")
        print(final_response.choices[0].message.content)
    else:
        print("\nסוכן ONYX:")
        print(response_message.content)

if __name__ == "__main__":
    # אנחנו מדמים כאן הודעה מלקוח בטלגרם או באתר
    test_message = "היי, אני צריך הצעת מחיר לטיסה פרטית מלונדון לניס ב-15 בספטמבר ל-4 נוסעים. מה האפשרויות?"
    run_onyx_agent(test_message)
