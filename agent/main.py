from datetime import datetime, timedelta
from langgraph.graph import StateGraph, END, START
from langgraph.types import Send
from langsmith import Client
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict, Annotated
from typing import Literal, Any

logger = getLogger(__name__)
llm = init_chat_model(
    "openai:gpt-5-nano",
    temperature=0.7,
    max_tokens=1000,
    configurable_fields=("temperature", "max_tokens", "model"),
)

class State(TypedDict):
    query: str
    auth: dict
    success: bool
    request: Literal["show-event", "show-schedule", "create-event", "update-event", "delete-event", "no-action"]
    metadata: dict[str, Any]

class OutputState(TypedDict):
    success: bool
    request: Literal["show-event", "show-schedule", "create-event", "update-event", "delete-event", "no-action"]
    metadata: dict[str, Any]

def llm_step(state: State) -> dict:
    # use an llm to parse the users intent from the query str
    # it should pick the type of request that needs to be made of the 6 available
    # and it should return that
    # the prompt should go in prompts.py 
    # and you should use langchain structured output to go from natural language to schema/type 

def show_event():
    #  return sth like:
#  {
# 	"success": "true",
# 	"request": "show-event",
# 	"metadata": {
# 		"event-id": "123",
# 		"calendar-id": "123"
# 	}
# } 



def show_schedule():
    # what am i doing between..
    # will return to fe info needed to make a request
    # parse from what am i doing next weekend to the start-date and end-date of next weekend
    update = {"metadata": {
            "start-date" : ...
            "end-date": 
        }
    }
    return update

def create_event():
    # return all the info needed to create the event the user wants
    # you are allowed to update title, location, attendees
    # the same way as above, return this as metadata
    pass

def update_event():
    # 	"metadata": {
	# 	"event-id": "123",
	# 	"calendar-id": "123",
	# 	... all NEW event info ...
	# }
    pass



def delete_event():
    #	"metadata": {
# 		"event-id": "123",
# 		"calendar-id": "123"
# 	}
# }
    pass

def do_nothing():
    pass

graph_builder = StateGraph(State, output_schema=OutputState)
# need start and end edges. start is llm routing step. end can be aggregate results, catch error or return
# add enough logs please
graph_builder.add_node(...)
graph_builder.add_edge(..)
graph = graph_builder.compile()