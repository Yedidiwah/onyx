import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv("/root/onyx/.env")

MCP_TOKEN = os.getenv("VILLIERS_MCP_TOKEN")
MCP_URL = "https://mcp.villiers.ai/mcp"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

user_histories = {}

def call_villiers_mcp(tool_name, arguments):
    if tool_name == "request_jet_confirmation":
        
        # --- פתרון לתעלומת התאריך של Villiers ---
        # משכפלים את התאריך לשמות המשתנים שהשרת כנראה מצפה להם
        if "date" in arguments:
            arguments["departure_date"] = arguments["date"]
            arguments["departureDate"] = arguments["date"]
            
        # --- מעקף Sandbox מדויק ---
        if arguments.get("email") == "sandbox-test@mail.villiers.ai":
            arguments["first_name"] = "Sandbox"
            arguments["last_name"] = "Test"
            arguments["phone"] = "+1 555 0100"
            
            # וידוא הרמטי: אם איכשהו חסר תאריך בטסט, נשתול אחד אוטומטית
            if "date" not in arguments:
                arguments["date"] = "2026-12-01"
                arguments["departure_date"] = "2026-12-01"
                arguments["departureDate"] = "2026-12-01"
        else:
            if not arguments.get("last_name"):
                arguments["last_name"] = "Guest"
            
            phone = arguments.get("phone", "")
            if phone and not phone.startswith("+"):
                arguments["phone"] = "+" + phone.lstrip("0")

    headers = {
        "Authorization": f"Bearer {MCP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    # הדפסות הלוג 
    print(f"--- MCP Request to {tool_name} ---")
    print(f"Payload: {payload}")
    
    try:
        response = requests.post(MCP_URL, headers=headers, json=payload)
        print(f"Response: {response.text}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        err_msg = f"API Error: {str(e)} | Details: {response.text if 'response' in locals() else 'No response'}"
        print(err_msg)
        return {"error": err_msg}

def run_onyx_agent(chat_id, user_message):
    chat_id_str = str(chat_id)
    
    system_prompt = """
    You are the luxury private jet concierge for ONYX (flywithonyx.com).
    
    STRICT WORKFLOW - YOU MUST FOLLOW THESE STEPS IN ORDER:

    STEP 0: If you do not yet know the origin, destination and date, ask for them in plain, natural language using CITY NAMES (e.g. "Where are you flying from and to, and on what date?"). NEVER ask the user to provide an IATA airport code themselves - that is your job to resolve internally per the AIRPORTS rule below, once they tell you a city.

    STEP 1: When a user asks for a flight, call `get_jet_estimate`.
    
    STEP 2: Display the estimated prices to the user. 
    CRITICAL: The API returns a generic link saying "Next step - Get confirmed live pricing". IGNORE THIS LINK COMPLETELY. DO NOT send any links at this stage. Instead, explicitly ask the user: "To get a confirmed live quote, please provide your First Name, Email, and Phone number."
    
    STEP 3: Once the user provides their details, immediately call `request_jet_confirmation`. Ensure you pass the correct `origin`, `destination`, and the `date` of the flight.
    
    STEP 4: After `request_jet_confirmation` is complete (whether successful or error due to limits), politely explain the result and NOW provide your exact affiliate link: [Book Direct with Villiers](https://www.villiers.ai/?id=ADHUHR).
    
    RULES:
    - LANGUAGE (CRITICAL): You MUST communicate entirely in the exact language the user uses. If the user writes in Hebrew, your ENTIRE response (including API results, jet categories, prices, and descriptions) MUST be translated to perfect Hebrew. Never copy-paste English API text to a non-English speaker.
    - AIRPORTS & MULTIPLE AIRPORTS: Translate cities strictly to active 3-letter IATA codes. If a user asks for a city with multiple airports (e.g., London, Paris, New York), automatically default to the primary international hub (e.g., LHR for London, CDG for Paris, JFK for New York) to generate the API estimate. In your response, politely mention which exact airport you selected.
    - TONE: Maintain a professional, high-end, luxurious tone.
    """

    if chat_id_str not in user_histories:
        user_histories[chat_id_str] = [{"role": "system", "content": system_prompt}]

    user_histories[chat_id_str].append({"role": "user", "content": user_message})

    if len(user_histories[chat_id_str]) > 15:
        user_histories[chat_id_str] = [user_histories[chat_id_str][0]] + user_histories[chat_id_str][-14:]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_jet_estimate",
                "description": "Instant indicative charter price range for a route.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string", "description": "3-letter IATA code (e.g. LHR)"},
                        "destination": {"type": "string", "description": "3-letter IATA code (e.g. CDG)"},
                        "date": {"type": "string", "description": "YYYY-MM-DD"},
                        "passengers": {"type": "integer"}
                    },
                    "required": ["origin", "destination", "date"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "request_jet_confirmation",
                "description": "Submit booking lead.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string"},
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "phone": {"type": "string"},
                        "origin": {"type": "string", "description": "3-letter IATA code of origin"},
                        "destination": {"type": "string", "description": "3-letter IATA code of destination"},
                        "date": {"type": "string", "description": "YYYY-MM-DD of departure"}
                    },
                    "required": ["email", "first_name", "phone", "origin", "destination", "date"]
                }
            }
        }
    ]

    target_tool_choice = "auto"
    if "@" in user_message and "." in user_message:
        target_tool_choice = {"type": "function", "function": {"name": "request_jet_confirmation"}}

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=user_histories[chat_id_str],
            tools=tools,
            tool_choice=target_tool_choice
        )

        response_message = response.choices[0].message

        if response_message.tool_calls:
            user_histories[chat_id_str].append(response_message)
            tool_call = response_message.tool_calls[0]
            arguments = json.loads(tool_call.function.arguments)
            
            function_response = call_villiers_mcp(tool_call.function.name, arguments)
            
            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_call.function.name,
                "content": json.dumps(function_response)
            }
            user_histories[chat_id_str].append(tool_msg)
            
            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=user_histories[chat_id_str]
            )
            final_message = final_response.choices[0].message.content
            user_histories[chat_id_str].append({"role": "assistant", "content": final_message})
            return final_message
        else:
            final_message = response_message.content
            user_histories[chat_id_str].append({"role": "assistant", "content": final_message})
            return final_message
            
    except Exception as e:
        print(f"Agent Logic Error: {e}")
        raise e
