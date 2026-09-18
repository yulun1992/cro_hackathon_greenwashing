"""Whitespace and lexical normalization shared by retrieval and validation."""
import re

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


STOP_WORDS = set("the a an and or of to in for by our we all is are was were be with from on as at this that shall must should company claim claims".split())


def tokens(text: str) -> set[str]:
    english = set(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS
    chinese = re.findall(r"[\u4e00-\u9fff]", text)
    return english | set("".join(chinese[i:i+2]) for i in range(len(chinese)-1))
