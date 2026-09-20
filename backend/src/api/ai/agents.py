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
        prompt="You are a helpful assistant for my managing my email inbox for generating, sending and reviewing emails.",
        name="email_agent"
    )

    return agent

# agent.invoke({"messages": "research the health benefits of running and draft an email about it"}, config={"configurable": {"additional_field": "123"}})    
def get_research_agent():
    model = get_openai_llm()
    agent = create_react_agent (
        model=model,
        tools=[research_email],
        name ='research_agent',
    )

    return agent


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
            "You manage a research assistant and an"
            "email inbox manager assistant. Assign work to them"            
        )
        
    ).compile()

    return supe