"""Small text helpers shared by the notes and Q&A gates.

Keeping these in one place means the relevance gate, the definition check and
any future judge all agree on what counts as a meaningful word.
"""

from __future__ import annotations

from app.transcript_index import norm

STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those there here
    is are was were be been being do does did doing done have has had having
    i you he she it we they me him her us them my your his its our their
    of in on at to for from by with about into over after before between
    as so such not no nor can could should would may might must will shall
    what which who whom whose when where why how
    also just very more most much many some any all each other another
    """.split()
)

# Connectives and light verbs that carry no lecture content. They shape an
# answer but say nothing about the subject, so counting them as ungrounded
# vocabulary makes a faithful paraphrase look like outside knowledge.
DISCOURSE_WORDS = frozenset(
    """
    because cause causes caused causing since therefore thus however instead
    toward towards away become becomes became becoming move moves moved moving
    big bigger biggest also really actually basically simply
    """.split()
)

# Words a student uses to ask about the lecture rather than to name a concept.
GENERIC_QUESTION_WORDS = frozenset(
    """
    lecturer lecture professor teacher speaker video clip talk talks talked
    explain explains explained say says said tell tells told mean means meant
    discuss discusses discussed mention mentions mentioned describe described
    cover covers covered according note notes point points idea ideas thing things
    confirm confirms confirmed confirming transcript transcripts text texts
    conversation dialogue recording audio quote quotes passage
    beginning end ending earlier later above below
    """.split()
)


def stem(word: str) -> str:
    """Fold common English inflections so overlap is about meaning, not endings.

    Deliberately small: it must treat "update/updates/updated" and
    "learning/learns/learned" as one word without inventing stems that merge
    unrelated terms. Irregular forms ("take"/"taken") are left alone.
    """
    folded = word
    if len(folded) > 4 and folded.endswith("ies"):
        folded = folded[:-3] + "y"
    elif len(folded) > 4 and folded.endswith("ied"):
        # "fried"/"studied" fold to "fry"/"study", so a question asked in the
        # base form still overlaps a transcript that used the past tense.
        folded = folded[:-3] + "y"
    elif len(folded) > 4 and folded.endswith(("sses", "shes", "ches", "xes")):
        folded = folded[:-2]
    elif len(folded) > 3 and folded.endswith("s") and not folded.endswith(("ss", "us", "is")):
        folded = folded[:-1]
    if len(folded) > 5 and folded.endswith("ing"):
        folded = folded[:-3]
    elif len(folded) > 4 and folded.endswith("ed"):
        folded = folded[:-2]
    if len(folded) > 3 and folded.endswith("e"):
        folded = folded[:-1]
    return folded


def content_words(text: str) -> set[str]:
    """Normalised, inflected-folded words that carry meaning, for overlap checks."""
    return {
        stem(word)
        for word in norm(text).split()
        if word not in STOPWORDS
        and word not in GENERIC_QUESTION_WORDS
        and word not in DISCOURSE_WORDS
        and (len(word) > 1 or word.isdigit())
    }
