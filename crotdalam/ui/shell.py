"""Safe command shell: no eval, subprocess, OS escapes or pipe execution."""

import cmd
import shlex


class InvestigationShell(cmd.Cmd):
    intro = "Crotdalam investigation shell. Type help; exit to leave. No OS commands."
    prompt = "crotdalam> "
    commands = ("search", "analyze", "report", "crawl", "validate", "extract", "correlate", "config", "session", "proxy", "monitor")

    def __init__(self, corpus=None, database=None):
        super().__init__()
        self.options = []
        for key, value in (("--corpus", corpus), ("--database", database)):
            if value:
                self.options.extend((key, value))
        self.history = []
        try:
            import readline
        except ImportError:
            self.readline = None
        else:
            self.readline = readline
            readline.set_history_length(500)

    def precmd(self, line):
        if line.strip():
            self.history.append(line)
            self.history = self.history[-500:]
        return line

    def emptyline(self):
        return None

    def default(self, line):
        from .cli import main
        try:
            tokens = shlex.split(line)
            if not tokens or tokens[0] not in self.commands:
                self.stdout.write("Unknown command. Type help.\n")
                return
            main(self.options + tokens)
        except (ValueError, SystemExit) as exc:
            if isinstance(exc, ValueError):
                self.stdout.write(f"Invalid command: {exc}\n")

    def completenames(self, text, *ignored):
        return sorted({name for name in (*self.commands, "history", "help", "exit", "quit") if name.startswith(text)})

    def completedefault(self, text, line, begidx, endidx):
        flags = ("--keyword", "--username", "--input", "--output", "--format", "--corpus", "--database", "--limit", "--csv", "--threads", "--rounds", "--interval", "--case-id", "--analyst", "--file")
        return [flag for flag in flags if flag.startswith(text)]

    def do_help(self, arg):
        """Show commands, or help search/report/etc."""
        if arg in self.commands:
            self.default(arg + " --help")
        else:
            self.stdout.write("Commands: " + ", ".join(self.commands) + ", history, exit\nUse help COMMAND for options. History is memory-only.\n")

    def do_history(self, arg):
        """Show in-memory command history."""
        for index, line in enumerate(self.history, 1):
            self.stdout.write(f"{index:3} {line}\n")

    def do_exit(self, arg):
        """Leave the shell."""
        return True

    do_quit = do_exit
    do_EOF = do_exit
