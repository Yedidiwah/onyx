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
    # וידוא ששדות חסרים לא מפילים את הקריאה
    if tool_name == "request_jet_confirmation":
        if not arguments.get("last_name"):
            arguments["last_name"] = "Guest"

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
    try:
        response = requests.post(MCP_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def run_onyx_agent(chat_id, user_message):
    chat_id_str = str(chat_id)
    
    system_prompt = """
    You are the luxury private jet concierge for ONYX (flywithonyx.com).
    Your goal is to provide exceptional, high-end customer service.
    
    MANDATORY INTEGRATION RULES:
    1. You must call `get_jet_estimate` and display the price range to the user before calling `request_jet_confirmation`.
    2. Use `search_empty_legs` if the user is looking for discounted empty-leg deals.
    3. As soon as the user provides their contact details (name, email, phone) and confirms the route, immediately invoke `request_jet_confirmation` without asking unnecessary follow-up questions. If last name is missing, use "Guest".
    
    AIRPORT & CITY TRANSLATION:
    - Accurately translate cities to 3-letter IATA codes. 
    - For cities with multiple airports (like London, Paris, Rome, New York, etc.), use the primary main hub by default (e.g., London -> LHR, Paris -> CDG, Rome -> FCO, New York -> JFK) unless specified otherwise.
    
    Always reply in a professional, luxurious tone. If the user writes in Hebrew, reply in Hebrew.
    """

    if chat_id_str not in user_histories:
        user_histories[chat_id_str] = [
            {"role": "system", "content": system_prompt}
        ]

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
                        "origin": {"type": "string", "description": "3-letter IATA airport code for origin"},
                        "destination": {"type": "string", "description": "3-letter IATA airport code for destination"},
                        "date": {"type": "string", "description": "Date of flight in YYYY-MM-DD format"},
                        "passengers": {"type": "integer", "description": "Number of passengers"}
                    },
                    "required": ["origin", "destination", "date"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_empty_legs",
                "description": "Find discounted empty-leg repositioning flights.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "request_jet_confirmation",
                "description": "Request confirmed live pricing by email (creates a booking lead).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string", "description": "User email address"},
                        "first_name": {"type": "string", "description": "User first name"},
                        "last_name": {"type": "string", "description": "User last name (optional)"},
                        "phone": {"type": "string", "description": "User phone number"},
                        "route": {"type": "string", "description": "Route description or IATA codes, e.g. FCO - BER"}
                    },
                    "required": ["email", "first_name", "phone", "route"]
                }
            }
        }
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=user_histories[chat_id_str],
            tools=tools,
            tool_choice="auto"
        )

        response_message = response.choices[0].message

        if response_message.tool_calls:
            user_histories[chat_id_str].append(response_message)
            
            tool_call = response_message.tool_calls[0]
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            function_response = call_villiers_mcp(tool_name, arguments)
            
            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
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
