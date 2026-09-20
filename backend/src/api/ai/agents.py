from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from api.ai.llms import get_openai_llm
from api.ai.tools import send_an_email, get_unread_emails, research_email
 

EMAIL_TOOLS_LIST = [
    send_an_email,
    get_unread_emails
    
]

def get_email_agent():
    model = get_openai_llm()
    agent = create_react_agent (
        model=model,
        tools=EMAIL_TOOLS_LIST,
        prompt=(
            "You manage my email inbox. When asked to send an email, you MUST call "
            "the send_an_email tool with subject, content and to_email. "
            "Report exactly what the tool returned ('Sent email' or 'Not sent: ...')."
        ),
        name="email_agent"
    )

    return agent

# agent.invoke({"messages": "research the health benefits of running and draft an email about it"}, config={"configurable": {"additional_field": "123"}})    
def get_research_agent():
    model = get_openai_llm()
    return create_react_agent(
        model=model,
        tools=[research_email],
        prompt=(
            "You are a research assistant. Always use the research_email tool. "
            "You CANNOT send emails. Never say an email was sent. "
            "Return only the research results."
        ),
        name="research_agent",
    )


# supe = get_supervisor() 
# supe.invoke({"messages": [{"role": "user", "content": "find out how to cook a tomato then email to ibm777p2@gmail.com for guidance"}]})
def get_supervisor():
    llm = get_openai_llm()
    email_agent = get_email_agent()
    research_agent = get_research_agent()
    supe = create_supervisor(
        agents=[email_agent, research_agent],
        model = llm,
        prompt=(
            "You manage a research_agent and an email_agent. "
            "Only email_agent can send emails. "
            "If the user asks to send or email something, you MUST transfer to email_agent "
            "after research, passing the subject, content and recipient address. "
            "Never tell the user an email was sent unless email_agent reports 'Sent email'."            
        )
        
    ).compile()

    return supe