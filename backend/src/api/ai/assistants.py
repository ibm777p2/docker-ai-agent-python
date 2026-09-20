from api.ai.llms import get_openai_llm

from api.ai.tools import send_an_email, get_unread_emails
from langchain_core.messages import ToolMessage, SystemMessage, HumanMessage
MAX_TURNS = 5

EMAIL_TOOLS = {
    "send_an_email": send_an_email,
    "get_unread_emails": get_unread_emails, 
}


def email_assistant(query: str):
    llm_base = get_openai_llm()
    # bind_tools registers the schemas; the model only ever sees descriptions
    #llm=llm_base.bind_tools([send_mail, get_unread_emails])
    llm=llm_base.bind_tools(list(EMAIL_TOOLS.values()))

    messages = [
        
        SystemMessage("You are a helpful assistant for my managing my email inbox."),       
        HumanMessage( query),
    ]
    
    # --- agent harness: transport -> parse -> dispatch -> feed back -> stop ---
    for turn in range(MAX_TURNS):
        response =llm.invoke(messages) 
        messages.append(response)
        
        # parse: did the model request any tools?
        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            return response
        
        # dispatch: the model can only ask — this code decides and executes
        for call in tool_calls:
            fn = EMAIL_TOOLS.get(call["name"])
            if fn is None:
                result = f"Unknown tool: {call['name']}"
            else:
                try:
                    result = fn.invoke(call["args"])     
                except Exception as e:
                    result = f"Tool failed: {e}"
            # feed back: paired to the request by tool_call_id
            messages.append( ToolMessage(content = str(result), tool_call_id= call["id"])
            )
    # stop: hit the turn cap with tool calls still pending        
    return response