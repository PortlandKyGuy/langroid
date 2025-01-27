"""
Single agent to use to chat with a Retrieval-augmented LLM.
Repeat: User asks question -> LLM answers.
"""
import re
import typer
from rich import print
from rich.prompt import Prompt
import os

from langroid.agent.special.doc_chat_agent import (
    DocChatAgent,
    DocChatAgentConfig,
)
from langroid.parsing.parser import ParsingConfig, PdfParsingConfig, Splitter
from langroid.agent.task import Task
from langroid.parsing.urls import get_list_from_user
from langroid.utils.configuration import set_global, Settings
from langroid.utils.logging import setup_colored_logging

app = typer.Typer()

setup_colored_logging()
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def chat(config: DocChatAgentConfig) -> None:
    agent = DocChatAgent(config)
    n_deletes = agent.vecdb.clear_empty_collections()
    collections = agent.vecdb.list_collections()
    collection_name = "NEW"
    is_new_collection = False
    replace_collection = False
    if len(collections) > 0:
        n = len(collections)
        delete_str = f"(deleted {n_deletes} empty collections)" if n_deletes > 0 else ""
        print(f"Found {n} collections: {delete_str}")
        for i, option in enumerate(collections, start=1):
            print(f"{i}. {option}")
        while True:
            choice = Prompt.ask(
                f"Enter 1-{n} to select a collection, "
                "or hit ENTER to create a NEW collection, "
                "or -1 to DELETE ALL COLLECTIONS",
                default="0",
            )
            try:
                if -1 <= int(choice) <= n:
                    break
            except Exception:
                pass

        if choice == "-1":
            confirm = Prompt.ask(
                "Are you sure you want to delete all collections?",
                choices=["y", "n"],
                default="n",
            )
            if confirm == "y":
                agent.vecdb.clear_all_collections(really=True)
                collection_name = "NEW"

        if int(choice) > 0:
            collection_name = collections[int(choice) - 1]
            print(f"Using collection {collection_name}")
            choice = Prompt.ask(
                "Would you like to replace this collection?",
                choices=["y", "n"],
                default="n",
            )
            replace_collection = choice == "y"

    if collection_name == "NEW":
        is_new_collection = True
        collection_name = Prompt.ask(
            "What would you like to name the NEW collection?",
            default="doc-chat",
        )

    agent.vecdb.set_collection(collection_name, replace=replace_collection)

    print("[blue]Welcome to the document chatbot!")
    print("[cyan]Enter x or q to quit, or ? for evidence")
    default_urls_str = " (or leave empty for default URLs)" if is_new_collection else ""
    print(f"[blue]Enter some URLs or file/dir paths below {default_urls_str}")
    inputs = get_list_from_user()
    if len(inputs) == 0:
        if is_new_collection:
            inputs = config.default_paths
    agent.config.doc_paths = inputs
    agent.ingest()
    system_msg = Prompt.ask(
        """
    [blue] Tell me who I am; complete this sentence: You are...
    [or hit enter for default] 
    [blue] Human
    """,
        default="a helpful assistant.",
    )
    system_msg = re.sub("you are", "", system_msg, flags=re.IGNORECASE)
    task = Task(
        agent,
        llm_delegate=False,
        single_round=False,
        system_message="You are " + system_msg,
    )
    task.run()


@app.command()
def main(
    debug: bool = typer.Option(False, "--debug", "-d", help="debug mode"),
    nocache: bool = typer.Option(False, "--nocache", "-nc", help="don't use cache"),
    cache_type: str = typer.Option(
        "redis", "--cachetype", "-ct", help="redis or momento"
    ),
) -> None:
    config = DocChatAgentConfig(
        n_query_rephrases=0,
        cross_encoder_reranking_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        hypothetical_answer=False,
        parsing=ParsingConfig(  # modify as needed
            splitter=Splitter.TOKENS,
            chunk_size=1000,  # aim for this many tokens per chunk
            overlap=100,  # overlap between chunks
            max_chunks=10_000,
            # aim to have at least this many chars per chunk when
            # truncating due to punctuation
            min_chunk_chars=200,
            discard_chunk_chars=5,  # discard chunks with fewer than this many chars
            n_similar_docs=3,
            # NOTE: PDF parsing is extremely challenging, each library has its own
            # strengths and weaknesses. Try one that works for your use case.
            pdf=PdfParsingConfig(
                # alternatives: "haystack", "unstructured", "pdfplumber", "fitz"
                library="pdfplumber",
            ),
        ),
    )

    set_global(
        Settings(
            debug=debug,
            cache=not nocache,
            cache_type=cache_type,
        )
    )
    chat(config)


if __name__ == "__main__":
    app()
