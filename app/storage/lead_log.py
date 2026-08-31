from pathlib import Path

from app.domain.messages import Lead


class LeadLogStore:
    """Append-only log store for Lead records.

    The log directory is ensured once at construction time.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, lead: Lead) -> None:
        """Append one formatted line to the log file."""
        line = f"{lead.timestamp} | {lead.phone} | {lead.text}\n"
        with open(self._path, "a") as f:
            f.write(line)

    @property
    def path(self) -> Path:
        return self._path
