"""Offline tests for the shared word normalisation."""

from app.language import content_words, stem


def test_verb_inflections_fold_together():
    assert stem("updates") == stem("updated") == stem("update")
    assert stem("learning") == stem("learns") == stem("learn")


def test_plural_and_verb_forms_fold_together():
    assert stem("weights") == stem("weight")
    assert stem("sizes") == stem("size")
    assert stem("diverged") == stem("diverges") == stem("diverge")


def test_protected_endings_are_left_alone():
    assert stem("loss") == "loss"
    assert stem("analysis") == "analysis"
    assert stem("class") == "class"


def test_content_words_drop_question_filler_and_stopwords():
    words = content_words("What does the lecturer mean by gradient descent?")
    assert words == {"gradient", "descent"}


def test_content_words_include_numbers():
    assert "1984" in content_words("written in 1984")


def test_ied_words_fold_to_the_base_form():
    assert stem("fried") == stem("fry")
    assert stem("studied") == stem("study")
    assert stem("applied") == stem("apply")


def test_meta_words_about_the_material_are_not_content_words():
    """"As confirmed earlier in the transcript" says nothing about the subject."""
    assert content_words("confirmed earlier in the transcript of the recording") == set()


def test_discourse_connectives_are_not_content_words():
    """Connectives phrase an answer but say nothing about the lecture."""
    assert content_words("because instead toward away become causing") == set()
