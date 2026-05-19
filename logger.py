import logging


class ContextFormatter(logging.Formatter):
    """Append common structured context keys when present."""

    CONTEXT_KEYS = ("citation_key", "arxiv_id", "stage", "exception_type")

    def format(self, record):
        base = super().format(record)
        parts = []
        for key in self.CONTEXT_KEYS:
            value = getattr(record, key, None)
            if value:
                parts.append(f"{key}={value}")
        if parts:
            return f"{base} | " + " ".join(parts)
        return base


def setup_logger(log_file="bibtex_dblp.log"):
    logger = logging.getLogger("BibTeXProcessor")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = ContextFormatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


logger = setup_logger()
