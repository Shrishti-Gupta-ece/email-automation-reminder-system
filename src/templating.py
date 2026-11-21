"""Load a template file and fill {{placeholders}} with real values."""
import re
from .config import TEMPLATES_DIR

PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def load_template(name: str):
    """Template format: first line 'Subject: ...', blank line, then the body."""
    path = TEMPLATES_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Template '{name}' not found in templates/")
    text = path.read_text(encoding="utf-8")
    first, _, body = text.partition("\n")
    if not first.lower().startswith("subject:"):
        raise ValueError(f"Template '{name}' must start with 'Subject:'")
    return first[len("subject:"):].strip(), body.strip()


def fill(text: str, values: dict) -> str:
    def repl(m):
        key = m.group(1)
        if key not in values:
            raise KeyError(f"Missing value for placeholder {{{{{key}}}}}")
        return str(values[key])
    return PLACEHOLDER.sub(repl, text)


def render(template_name: str, values: dict):
    subject_t, body_t = load_template(template_name)
    return fill(subject_t, values), fill(body_t, values)
