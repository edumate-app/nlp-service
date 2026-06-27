def best_source_transcript(transcript_list):
    all_t = list(transcript_list)

    for rule in [
        lambda t: not t.is_generated and t.language_code == "en",
        lambda t: not t.is_generated,
        lambda t: t.language_code == "en",
        lambda t: True,
    ]:
        filtered = [t for t in all_t if rule(t)]
        if filtered:
            return filtered[0]

    return None
