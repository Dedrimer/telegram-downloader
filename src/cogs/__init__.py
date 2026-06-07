from .downloader import button as button
from .downloader import download as download
from .downloader import single_group as single_group
from .downloader import status as status
from .error_handler import error_handler as error_handler
from .general import help_command as help_command
from .general import info as info
from .general import language as language
from .general import start as start
from .general import storage as storage

# Specify the commands for the bot
general_commands: list = [
    help_command,
    info,
    language,
    start,
    storage
]

downloader_commands: list = [
    button,
    download,
    single_group,
    status,
]

__all__ = [
    "downloader_commands",
    "error_handler",
    "general_commands",
]
