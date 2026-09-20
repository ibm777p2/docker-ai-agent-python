from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from api.emailer.sender import send_mail
from api.emailer.inbox_reader import read_inbox
from api.ai.services import generate_email_message

# Tool parameters come from the MODEL. RunnableConfig comes from YOUR code.
# Put identity (user_id) in config — the model can't see or change it.
#
#   example
#   agent.invoke({"messages": query},
#                config={"configurable": {"user_id": user.id}})

@tool
def research_email(query: str, config: RunnableConfig):
    """
    Perform research based on the query
    
    Arguments:
    -query: str - Topic of research
    """
    # from config, not the model, use user_id here in production
    # print(config)
    add_field = (config.get("configurable") or {}).get("additional_field")
    print('add_field', add_field)
    response = generate_email_message(query)
    msg = f"Subject {response.subject}:\nBody: {response.contents}"    
    return msg

@tool
def send_an_email(subject:str, content: str, to_email:str):
    """ 
    Send an email with a subject and content
    
    Arguments:
    - subject: str - Text subject of the email
    - content: str - Text body content of the email
    - to_email str - destination email address
     
    """
    try:
        send_mail(subject=subject, content=content, to_email=to_email)
    except Exception as e:
        return f"Not sent: {e}"
    return "Sent email"

@tool
def get_unread_emails(hours_ago:int=48) -> str:
    """
    Read all emails from my inbox within the last N hours  
    
    Arguments:
    - hours_ago: int = 24 - number of hours ago to retrieve in the inbox
    
    Returns:
    A string of emails separated by a line "----"
 
    """
    try:
        emails = read_inbox(hours_ago=hours_ago, verbose=False)
    except Exception as e:
        return f"Error reading email: {e}"
        
    cleaned = []
    
    for email in emails:
        print(email)
        data = email.copy()
        if "html_body" in data:
            data.pop('html_body')
        msg = ""
        for k, v in data.items():
            msg += f"{k}:\t{v}\n"
        cleaned.append(msg)
    return "\n-----\n".join(cleaned)[:500]
        