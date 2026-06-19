import test_symbols


TESTS = [
    test_symbols.test_written_symbol_names_remain_words,
    test_symbols.test_real_numbers_and_symbols_can_still_use_recordings,
    test_symbols.test_source_symbols_are_marked_without_confusing_written_names,
    test_symbols.test_nvda_pt_br_spelling_names_resolve_to_real_symbols,
    test_symbols.test_all_reported_symbols_have_dedicated_recordings,
]


if __name__ == "__main__":
    for test in TESTS:
        test()
        print("OK:", test.__name__)
    print(f"{len(TESTS)} testes concluídos com sucesso.")

