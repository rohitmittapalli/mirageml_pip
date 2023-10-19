import typer
import keyring
import time
import sys
import segment.analytics as analytics

from .constants import SERVICE_ID, ANALYTICS_WRITE_KEY, supabase
from .commands import (
    login, show_config, set_config, normal_chat, rag_chat,
    list_plugins, add_plugin, list_sources, add_source,
    sync_plugin, delete_source
)

analytics.write_key = ANALYTICS_WRITE_KEY
app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="markdown",
    help="""
    MirageML CLI.

    See the website at https://mirageml.com/ for documentation and more information
    about running code on MirageML.
    """,
)

config_app = typer.Typer(name="config", help="Manage the config", no_args_is_help=True)
add_app = typer.Typer(name="add", help="Add a new resource", no_args_is_help=True)
list_app = typer.Typer(name="list", help="List resources", no_args_is_help=True)
sync_app = typer.Typer(name="sync", help="Sync resources", no_args_is_help=True)
delete_app = typer.Typer(name="delete", help="Delete resources", no_args_is_help=True)

app.add_typer(config_app)
app.add_typer(add_app)
app.add_typer(list_app)
app.add_typer(sync_app)
app.add_typer(delete_app)


@app.callback()
def main(ctx: typer.Context):
    user_id = keyring.get_password(SERVICE_ID, 'user_id')
    refresh_token = keyring.get_password(SERVICE_ID, 'refresh_token')
    expires_at = keyring.get_password(SERVICE_ID, 'expires_at')
    if not user_id and ctx.invoked_subcommand != "login":
        typer.echo("Please login first. Run `mirageml login`")
        raise typer.Exit()
    elif expires_at and float(expires_at) < time.time() and ctx.invoked_subcommand != "login":
        try:
            response = supabase.auth._refresh_access_token(refresh_token)
            session = response.session
            keyring.set_password(SERVICE_ID, 'access_token', session.access_token)
            keyring.set_password(SERVICE_ID, 'refresh_token', session.refresh_token)
            keyring.set_password(SERVICE_ID, 'expires_at', str(session.expires_at))
            analytics.identify(user_id)
        except:
            typer.echo("Please login again. Run `mirageml login`")
            raise typer.Exit()

    full_command = " ".join(sys.argv[1:])
    analytics.track(user_id, "command", {"command": full_command})


@app.command(name="help", hidden=True)
def custom_help():
    # Your custom help message
    typer.echo("Your Custom Help Message Here")


@app.command(name="login")
def login_command():
    """Login to Mirage ML"""
    login()


@app.command()
def chat(file_path: str = typer.Argument(None, help="Path to a file to use as a chat history.")):
    """Chat with Mirage ML"""
    normal_chat(file_path=file_path)


@app.command()
def rag(sources: list[str] = typer.Argument(None, help="Sources to use for RAG")):
    """Chat with Mirage ML using RAG"""
    rag_chat()

@config_app.command(name="show")
def show_config_command():
    """Show the current config"""
    show_config()


@config_app.command(name="set")
def set_config_command():
    """
    Set the config file for MirageML
    """
    set_config()

# List Commands
@list_app.command(name="plugins")
def list_plugins_command():
    """List connected plugins"""
    list_plugins()


@list_app.command(name="sources")
def list_sources_command():
    """List created sources"""
    list_sources()

# Add Commands
@add_app.command(name="plugin")
def add_plugin_command(name: str):
    """Add a plugin by name"""
    add_plugin({"plugin": name})


@add_app.command(name="source")
def add_source_command():
    """Add a new source"""
    while True:
        link = input("Link for the source: ")
        if not link.startswith("https://"):
            typer.echo("Please enter a valid link starting with https://")
            continue
        break
    from urllib.parse import urlparse
    parsed_url = urlparse(link)
    name = parsed_url.netloc.split('.')[0]
    if name == "docs": name = parsed_url.netloc.split('.')[1]
    name = input(f"Name for the source [default: {name}]: ") or name
    remote = input("Store the source remotely? (y/n): ")
    remote = remote.lower().startswith("y")

    add_source(name, link, remote)

# Delete Commands
@delete_app.command(name="source")
def delete_source_command():
    """Delete a source"""
    from rich.prompt import Prompt
    name = Prompt.ask("Name of the source")
    remote = Prompt.ask("Is the source remote? (y/n)", default="n", show_default=True)
    remote = remote.lower().startswith("y")
    delete_source(name, remote)

# Sync Commands
@sync_app.command(name="plugin")
def sync_plugin_command(name: str):
    """Sync a plugin"""
    sync_plugin({"plugin": name})


if __name__ == "__main__":
    app()
