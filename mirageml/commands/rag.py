import sys

import typer
from rich.box import HORIZONTALS
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from .config import load_config
from .utils.custom_inputs import multiline_input
from .utils.llm import llm_call
from .utils.prompt_templates import RAG_TEMPLATE
from .utils.vectordb import (
    list_local_qdrant_db,
    list_remote_qdrant_db,
    local_qdrant_search,
    remote_qdrant_search,
    transient_qdrant_search,
)

console = Console()
config = load_config()


def search(live, user_input, sources, transient_sources=None):
    from concurrent.futures import ThreadPoolExecutor

    hits = []
    local = list_local_qdrant_db()
    remote = list_remote_qdrant_db()

    local_sources = [source for source in sources if source in local]
    remote_sources = [source for source in sources if source in remote]

    for source_name in local_sources:
        live.update(
            Panel(
                "Searching through local sources...",
                title="[bold blue]Assistant[/bold blue]",
                border_style="blue",
            )
        )
        try:
            # Search for matches in each source based on user input
            hits.extend(local_qdrant_search(source_name, user_input))
        except Exception:
            # Handle potential errors with mismatched embedding models
            error_msg_local = f"Source: {source_name} was created with OpenAI's embedding model. Please run with `local_mode=False` or reindex with `mirageml delete source {source_name}; mirageml add source {source_name}`."
            error_msg_openai = f"Source: {source_name} was created with a local embedding model. Please run with `local_mode=True` or reindex with `mirageml delete source {source_name}; mirageml add source {source_name}`."

            typer.secho(
                error_msg_local if config["local_mode"] else error_msg_openai,
                fg=typer.colors.RED,
                bold=True,
            )
            return

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(remote_qdrant_search, source_name, user_input) for source_name in remote_sources]
        live.update(
            Panel(
                "Searching through remote sources...",
                title="[bold blue]Assistant[/bold blue]",
                border_style="blue",
            )
        )

        for future in futures:
            try:
                hits.extend(future.result())
            except Exception:
                error_msg = f"Failed to search in source: {source_name}. Try again! You may need to re-add the source with mirage add source"
                typer.secho(
                    error_msg,
                    fg=typer.colors.RED,
                    bold=True,
                )

    if transient_sources:
        live.update(
            Panel(
                "Searching through files and urls...",
                title="[bold blue]Assistant[/bold blue]",
                border_style="blue",
            )
        )
        if config["local_mode"]:
            for data, metadata in transient_sources:
                hits.extend(transient_qdrant_search(user_input, data, metadata))
                live.update(
                    Panel(
                        "Searching through files and urls...",
                        title="[bold blue]Assistant[/bold blue]",
                        border_style="blue",
                    )
                )
        else:
            source_name = "transient"
            with ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(remote_qdrant_search, source_name, user_input, data, metadata)
                    for data, metadata in transient_sources
                ]

                for future in futures:
                    hits.extend(future.result())

    return hits


def rank_hits(hits):
    # Rank the hits based on their relevance
    sorted_hits = sorted(hits, key=lambda x: x["score"], reverse=True)[:10]
    return sorted_hits


def create_context(sorted_hits):
    return "\n\n".join([str(x["payload"]["source"]) + ": " + x["payload"]["data"] for x in sorted_hits])


def search_and_rank(live, user_input, sources, transient_sources):
    hits = search(live, user_input, sources, transient_sources)
    sorted_hits = rank_hits(hits)
    return sorted_hits


def rag_chat(sources, transient_sources):
    try:
        all_sources = sources + [x[1][0]["source"] for x in transient_sources]
        user_input = multiline_input(f"Ask a question over these sources ({', '.join(all_sources)})")
        if user_input.lower().strip() == "exit":
            typer.secho("Ending chat. Goodbye!", fg=typer.colors.BRIGHT_GREEN, bold=True)
            sys.exit()
    except KeyboardInterrupt:
        typer.secho("Ending chat. Goodbye!", fg=typer.colors.BRIGHT_GREEN, bold=True)
        sys.exit()

    # Live display while searching for relevant sources
    with Live(
        Panel(
            "Searching through the relevant sources...",
            title="[bold blue]Assistant[/bold blue]",
            border_style="blue",
        ),
        console=console,
        transient=True,
        auto_refresh=True,
        refresh_per_second=8,
    ) as live:
        sorted_hits = search_and_rank(live, user_input, sources, transient_sources)
        sources_used = list(set([hit["payload"]["source"] for hit in sorted_hits]))
        context = create_context(sorted_hits)

        # Chat history that will be sent to the AI model
        chat_history = [
            {
                "role": "system",
                "content": "You are a helpful assistant. When responding to questions, provide answers concisely using the following format:\n{answer}\n\nSources:\n{sources}",
            },
            {
                "role": "user",
                "content": RAG_TEMPLATE.format(context=context, question=user_input, sources=sources_used),
            },
        ]

        # Fetch the AI's response
        ai_response = ""
        try:
            live.update(
                Panel(
                    "Found relevant sources! Answering question...",
                    title="[bold blue]Assistant[/bold blue]",
                    box=HORIZONTALS,
                    border_style="blue",
                )
            )
            response = llm_call(
                chat_history,
                model=config["model"],
                stream=True,
                local=config["local_mode"],
            )

            if config["local_mode"]:
                for chunk in response:
                    ai_response += chunk
                    live.update(
                        Panel(
                            Markdown(ai_response),
                            title="[bold blue]Assistant[/bold blue]",
                            box=HORIZONTALS,
                            border_style="blue",
                        )
                    )
            else:
                for chunk in response.iter_content(chunk_size=512):
                    if chunk:
                        decoded_chunk = chunk.decode("utf-8")
                        ai_response += decoded_chunk
                        live.update(
                            Panel(
                                Markdown(ai_response),
                                title="[bold blue]Assistant[/bold blue]",
                                box=HORIZONTALS,
                                border_style="blue",
                            )
                        )
        except KeyboardInterrupt:
            pass
    return chat_history, ai_response
