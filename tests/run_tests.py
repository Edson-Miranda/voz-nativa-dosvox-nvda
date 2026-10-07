import test_core


TESTS = [
    test_core.test_manifest_and_package_metadata,
    test_core.test_voice_variants_and_data_layout,
    test_core.test_number_expansion,
    test_core.test_recorded_ascii_symbols_and_space,
    test_core.test_fast_letters_are_available,
    test_core.test_ini_fallback_matches_standard_parser,
    test_core.test_core_import_without_host_configparser,
]


if __name__ == "__main__":
    for test in TESTS:
        test()
        print("OK:", test.__name__)
    print(f"{len(TESTS)} testes concluídos com sucesso.")