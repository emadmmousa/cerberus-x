"""Tests for API-side result enrichment."""

from orchestrator.database import get_results, init_db, save_phase_result


def test_get_results_enriches_legacy_sqlmap_rows(tmp_path, monkeypatch):
    db = tmp_path / "results.db"
    out = tmp_path / "output"
    out.mkdir()
    monkeypatch.setattr("orchestrator.database.DB_PATH", str(db))
    monkeypatch.setenv("FIREBREAK_OUTPUT_DIR", str(out))
    monkeypatch.setattr(
        "orchestrator.database.export_target_reports",
        lambda *_args, **_kwargs: {"json": str(out / "x.json"), "html": str(out / "x.html")},
    )
    init_db()

    save_phase_result(
        "distrokid.com",
        "db access crawl deep s6",
        [
            {
                "tool": "sqlmap",
                "target": "https://distrokid.com",
                "vulnerable": False,
                "raw_output": (
                    "[10:27:19] [INFO] starting crawler for target URL "
                    "'https://distrokid.com'\n"
                    "[10:27:19] [WARNING] no usable links found "
                    "(with GET parameters) or forms\n"
                ),
            }
        ],
        job_id="job-enrich",
    )

    rows = get_results("distrokid.com", job_id="job-enrich")
    assert len(rows) == 1
    result = rows[0]["result"]
    assert result["partial"] is True
    assert result["no_injection_surface"] is True
    assert "inconclusive" in str(result.get("note", "")).lower()


def test_enrich_result_rows_adds_flags_to_api_shape():
    from tools.result_enrichment import enrich_result_rows

    rows = enrich_result_rows(
        [
            {
                "tool": "sqlmap",
                "phase": "db access union only s7",
                "result": {
                    "tool": "sqlmap",
                    "vulnerable": False,
                    "raw_output": (
                        "[10:29:28] [WARNING] no usable links found "
                        "(with GET parameters) or forms\n"
                    ),
                },
            }
        ]
    )
    assert rows[0]["result"]["partial"] is True


def test_enrich_metasploit_invalid_module_code():
    from tools.result_enrichment import enrich_tool_result

    enriched = enrich_tool_result(
        "metasploit",
        {
            "tool": "metasploit",
            "code": "rpc_error",
            "error": "Invalid Module",
            "module": "exploit/linux/http/panos_telemetry_cmd_exec",
        },
    )
    assert enriched["code"] == "invalid_module"
