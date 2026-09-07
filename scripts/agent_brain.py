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
        
        # --- מעקף Sandbox מדויק ---
        if arguments.get("email") == "sandbox-test@mail.villiers.ai":
            arguments["first_name"] = "Sandbox"
            arguments["last_name"] = "Test"
            arguments["phone"] = "+1 555 0100"
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
    
    # הדפסות הלוג (קריטי לדיבאג בשרת)
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
    
    STEP 1: When a user asks for a flight, call `get_jet_estimate`. 
    
    STEP 2: Display the estimated prices to the user in their language. 
    CRITICAL: The API returns a generic link saying "Next step - Get confirmed live pricing". IGNORE THIS LINK COMPLETELY. DO NOT send any links at this stage. Instead, explicitly ask the user: "To get a confirmed live quote, please provide your First Name, Email, and Phone number."
    
    STEP 3: Once the user provides their details, immediately call `request_jet_confirmation`. Ensure you pass the correct `origin` and `destination` 3-letter IATA codes.
    
    STEP 4: After `request_jet_confirmation` is complete (whether successful or error due to limits), politely explain the result and NOW provide your exact affiliate link: [Book Direct with Villiers](https://www.villiers.ai/?id=ADHUHR).
    
    RULES:
    - AIRPORTS: Translate cities strictly to active 3-letter IATA codes (e.g., Rome -> FCO, London -> LHR, Paris -> CDG).
    - TRANSLATION: The API returns English results. You MUST translate the prices, descriptions, and jet types into the user's language before sending the message. Do NOT copy-paste English API output to a user speaking another language.
    - TONE: Maintain a professional, high-end, luxurious tone.
    """

    if chat_id_str not in user_histories:
        user_histories[chat_id_str] = [{"role": "system", "content": system_prompt}]

    user_histories[chat_id_str].append({"role": "user", "content": user_message})

    # שמירה על זיכרון שיחה נקי (15 הודעות אחרונות)
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
                        "destination": {"type": "string", "description": "3-letter IATA code of destination"}
                    },
                    "required": ["email", "first_name", "phone", "origin", "destination"]
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
