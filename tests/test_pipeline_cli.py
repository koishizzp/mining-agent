from thermo_mining.pipeline import should_skip_stage


def test_should_skip_stage_respects_done_json(tmp_path):
    done_path = tmp_path / "DONE.json"
    done_path.write_text(
        '{"stage_name":"01_prefilter","input_hash":"abc","parameters":{},"software_version":"0.1.0","runtime_seconds":1.0,"retain_count":1,"reject_count":0}',
        encoding="utf-8",
    )

    assert should_skip_stage(done_path=done_path, expected_input_hash="abc", resume=True) is True
    assert should_skip_stage(done_path=done_path, expected_input_hash="xyz", resume=True) is False
    assert should_skip_stage(done_path=done_path, expected_input_hash="abc", resume=False) is False
