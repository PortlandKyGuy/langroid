from llmagent.language_models.base import LLMMessage, Role, StreamingIfAllowed
from llmagent.agent.base import Agent, AgentConfig
from llmagent.mytypes import Document
from typing import List, Optional
from rich import print


class ChatAgent(Agent):
    """
    Chat Agent interacting with external env
    (could be human, or external tools).
    The agent (the LLM actually) is provided with a "Task Spec", and told to think in
    small steps. It may be given a set of possible "Actions", and if so it is told to
    emit the appropriate action in each round. Each round consists of:
    - LLM emits an Action, or says Done
    - LLM receives an Observation from that Action
        (which could be a human response but not necessarily)
    - LLM thinks
    """

    def __init__(self, config: AgentConfig, task: Optional[List[LLMMessage]] = None):
        """
        Chat-mode agent initialized with task spec as the initial message sequence
        Args:
            config: settings for the agent
            task: seq of messages to start with. If empty a "system" msg is
                constructed by default.
                Note these messages are not yet issued to LLM at agent init.

        !!! note
             `self.message_history` is different from `self.dialog` (in Agent class):

            - `self.message_history` is the sequence of messages sent to the LLM in
            **chat mode** (e.g. when using OpenAI `ChatCompletion.create()`)
                Typically we send a sequence of such messages to "prime"
            the LLM context for some task, and we extend and re-send this sequence to
            continue interaction. Note that consecutive messages in the sequence could
            have different or same roles (e.g. "user", "assistant"). Each message has a
            "dict" structure, which we call :class:`LLMMessage`.

            - `self.dialog` is the sequence of `(prompt, response)` tuples produced
            when interacting with an LLM in **completion mode**,
            where `prompt (str)` is sent TO the LLM, and `response (str)` is received
            FROM the LLM. Typically as an LLM conversation goes on, we collate
            `self.dialog` into a single string, and insert it into the context part
            of the next prompt to the LLM.

        """
        super().__init__(config)
        self.message_history: List[LLMMessage] = []
        if task is None:
            task = [LLMMessage(role=Role.SYSTEM, content="You are a helpful assistant")]
        self.task_messages = task

    def run(self):
        llm_msg = self.start().content
        while True:
            agent_result = self.handle_message(llm_msg)
            if agent_result is None:
                llm_msg = self.respond(
                    """
                    If your question fits one of the JSON templates I gave, 
                    rewrite using that format please
                    """
                ).content
                agent_result = self.handle_message(llm_msg)
            if agent_result is not None:
                msg = f"{agent_result}"
                print(f"[red]Agent: {agent_result}")
            else:
                print("\n[blue]Human: ", end="")
                msg = input("")
            if msg in ["exit", "quit", "q", "x", "bye"]:
                print("[green] Bye, hope this was useful!")
                break
            llm_msg = self.respond(msg).content

    def start(self) -> Document:
        """
        Start the agent, by sending the initial task spec to LLM
        Returns:
            Document (i.e. with fields "content", "metadata")
        """
        with StreamingIfAllowed(self.llm):
            response = self.respond_messages(self.task_messages)
        self.message_history = self.task_messages + [
            LLMMessage(
                role=Role.ASSISTANT,
                content=response.content,
            )
        ]
        return Document(content=response.content, metadata=response.metadata)

    def respond(self, message: str) -> Document:
        """
        Respond to a single user message, appended to the message history,
        in "chat" mode
        Args:
            message: user message
        Returns:
        """
        self.message_history.append(LLMMessage(role=Role.USER, content=message))
        with StreamingIfAllowed(self.llm):
            response = self.respond_messages(self.message_history)
        self.message_history.append(
            LLMMessage(role=Role.ASSISTANT, content=response.content)
        )
        return Document(content=response.content, metadata=response.metadata)
