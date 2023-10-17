import argparse
import keyring
import time

from .commands import login, chat, rag_chat, list_plugins, add_plugin, list_sources, add_source, sync_plugin
from .constants import SERVICE_ID, supabase

def main():
    parser = argparse.ArgumentParser(description="Mirage ML CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser('login', help='Login to Mirage ML')
    subparsers.add_parser('chat', help='Chat with Mirage ML')

    # RAG Parser
    rag_parser = subparsers.add_parser('rag', help='Chat with Mirage ML using RAG')
    rag_parser.add_argument('-s', '--sources', nargs='+', default=["local"],
                            help='Sources to search for answers, specify `local` to index local files.')

    # List Parser
    list_parser = subparsers.add_parser('list', help='List resources')
    list_subparser = list_parser.add_subparsers(dest="subcommand")
    list_subparser.add_parser('plugins', help='List connected plugins')
    list_subparser.add_parser('sources', help='List created sources')

    # Add Parser
    add_parser = subparsers.add_parser('add', help='Add a new resource')
    add_subparser = add_parser.add_subparsers(dest="subcommand")
    ## Add Plugin
    add_plugin_parser = add_subparser.add_parser('plugin', help='Name of the plugin.')
    add_plugin_parser.add_argument('name', help='Name of the plugin. Supported plugins: notion')
    ## Add Source
    add_source_parser = add_subparser.add_parser('source', help='Add a new source')
    add_source_parser.add_argument('-n', '--name', help='Name of the source')
    add_source_parser.add_argument('-l', '--link', help='Link for the source')

    # Sync Parser
    sync_parser = subparsers.add_parser('sync', help='Sync resources')
    sync_subparser = sync_parser.add_subparsers(dest="subcommand")
    ## Sync Plugin
    sync_plugin_parser = sync_subparser.add_parser('plugin', help='Sync a plugin')
    sync_plugin_parser.add_argument('name', help='Name of the plugin. Supported plugins: notion')

    args = parser.parse_args()

    user_id = keyring.get_password(SERVICE_ID, 'user_id')
    refresh_token = keyring.get_password(SERVICE_ID, 'refresh_token')
    expires_at = keyring.get_password(SERVICE_ID, 'expires_at')

    if not user_id and args.command != "login":
        print("Please login first. Run `mirageml login`")
        return
    elif expires_at and float(expires_at) < time.time() and args.command != "login":
        try:
            response = supabase.auth._refresh_access_token(refresh_token)
            session = response.session
            keyring.set_password(SERVICE_ID, 'access_token', session.access_token)
            keyring.set_password(SERVICE_ID, 'refresh_token', session.refresh_token)
            keyring.set_password(SERVICE_ID, 'expires_at', str(session.expires_at))
        except:
            print("Please login again. Run `mirageml login`")
            return

    if args.command == "login":
        login()
    elif args.command == "chat":
        chat()
    elif args.command == "rag":
        rag_chat(args.sources)
    elif args.command == "list":
        if args.subcommand == "plugins":
            list_plugins()
        elif args.subcommand == "sources":
            list_sources()
        else:
            list_parser.print_help()
    elif args.command == "add":
        if args.subcommand == "plugin":
            add_plugin({ "plugin": args.name })
        elif args.subcommand == "source":
            add_source(args)
        else:
            add_parser.print_help()
    elif args.command == "sync" and args.subcommand == "plugin":
        sync_plugin({ "plugin": args.name })
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
