import os
import json
import re
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv("/root/onyx/.env")

MCP_TOKEN = os.getenv("VILLIERS_MCP_TOKEN")
MCP_URL = "https://mcp.villiers.ai/mcp"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

user_histories = {}
user_active_routes = {}

def call_villiers_mcp(tool_name, arguments):
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
    
    STRICT VILLIERS INTEGRATION PROTOCOL:
    1. ESTIMATE FIRST: Call `get_jet_estimate` and display the price range to the user. 
    2. NEVER output raw links or generic URLs (like villiers.ai) in your text responses.
    3. AFTER SHOWING THE ESTIMATE: You must explicitly ask the user for their contact details (First Name, Email, Phone Number) so you can submit a confirmed live pricing request on their behalf.
    4. ACTIVE AIRPORTS ONLY: Translate cities strictly to active 3-letter IATA codes. For multi-airport cities, use primary active hubs (Rome -> FCO, Berlin -> BER, London -> LHR, Paris -> CDG). NEVER use closed airports like TXL.
    5. LEAD SUBMISSION: Once the user provides their contact details, you must invoke the `request_jet_confirmation` tool immediately.
    
    Always reply in a professional, luxurious tone. If the user writes in Hebrew, reply in Hebrew.
    """

    if chat_id_str not in user_histories:
        user_histories[chat_id_str] = [{"role": "system", "content": system_prompt}]

    user_histories[chat_id_str].append({"role": "user", "content": user_message})

    # מנגנון הגנה דטרמיניסטי בפייתון ללכידת פרטי קשר והרצת ה-MCP
    is_contact_info = "@" in user_message or (any(char.isdigit() for char in user_message) and len(user_message) > 6)
    
    if is_contact_info and chat_id_str in user_active_routes:
        route_info = user_active_routes[chat_id_str]
        
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', user_message)
        email = email_match.group(0) if email_match else "sandbox-test@mail.villiers.ai"
        
        phone_digits = "".join(filter(lambda c: c.isdigit() or c == '+', user_message))
        if not phone_digits.startswith("+"):
            phone_digits = "+" + phone_digits.lstrip("0")
        phone = phone_digits if len(phone_digits) > 8 else "+972507400786"
        
        first_name = user_message.split()[0] if user_message.strip() else "Guest"
        if "@" in first_name or first_name.isdigit():
            first_name = "Yedidya"

        tool_args = {
            "email": email,
            "first_name": first_name,
            "last_name": "Guest",
            "phone": phone,
            "route": route_info
        }

        mcp_res = call_villiers_mcp("request_jet_confirmation", tool_args)
        print(f"Direct MCP Execution Result: {mcp_res}")

        del user_active_routes[chat_id_str]

        success_reply = (
            f"תודה רבה, {first_name}! פרטי ההזמנה שלך עבור המסלול ({route_info}) נקלטו בהצלחה והועברו לצוות הטיסות לפתיחת תיק אישור מול המפעילים.\n\n"
            "תוכל להמשיך לצפות ולנהל את כל הדילים הזמינים ישירות דרך פלטפורמת הפרימיום שלנו:\n"
            "🔗 https://www.villiers.ai/?id=ADHUHR\n\n"
            "אשמח לעמוד לשירותך בכל בקשה נוספת!"
        )
        user_histories[chat_id_str].append({"role": "assistant", "content": success_reply})
        return success_reply

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_jet_estimate",
                "description": "Instant indicative charter price range for a route.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string", "description": "3-letter active IATA code for origin (e.g. FCO)"},
                        "destination": {"type": "string", "description": "3-letter active IATA code for destination (e.g. BER)"},
                        "date": {"type": "string", "description": "Date of flight in YYYY-MM-DD format"},
                        "passengers": {"type": "integer", "description": "Number of passengers"}
                    },
                    "required": ["origin", "destination", "date"]
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
            arguments = json.loads(tool_call.function.arguments)
            
            if tool_call.function.name == "get_jet_estimate":
                orig = arguments.get("origin", "FCO")
                dest = arguments.get("destination", "BER")
                user_active_routes[chat_id_str] = f"{orig} to {dest}"

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
