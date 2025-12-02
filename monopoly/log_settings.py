from pathlib import Path

from monopoly.log import Log

project_root = Path(__file__).resolve().parent
results_dir = project_root.parent / "results"


class LogSettings:
    KEEP_GAME_LOG = True
    _run_dir = None
    EVENTS_LOG_PATH = results_dir / "events.log"
    BANKRUPTCIES_PATH = results_dir / "bankruptcies.tsv"

    @classmethod
    def init_logs(cls, run_dir=None):
        """Initiate & reset both logs; return (events_log, bankruptcies_log)."""
        if run_dir:
            cls._run_dir = Path(run_dir)
            cls.EVENTS_LOG_PATH = cls._run_dir / "events.log"
            cls.BANKRUPTCIES_PATH = cls._run_dir / "bankruptcies.tsv"
        else:
            cls._run_dir = None
            cls.EVENTS_LOG_PATH = results_dir / "events.log"
            cls.BANKRUPTCIES_PATH = results_dir / "bankruptcies.tsv"

        events_log = Log(cls.EVENTS_LOG_PATH, disabled=not cls.KEEP_GAME_LOG)
        events_log.reset("Events log")
        bankruptcies_log = Log(cls.BANKRUPTCIES_PATH)
        bankruptcies_log.reset("game_number\tplayer_bankrupt\tturn")
        return events_log, bankruptcies_log
    
    @classmethod
    def get_run_dir(cls):
        return cls._run_dir
