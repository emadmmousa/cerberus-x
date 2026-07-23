import subprocess

from tools.wrappers import (
    ffuf,
    gobuster,
    hydra,
    masscan,
    nmap,
    nuclei,
    rustscan,
    sqlmap,
)


def test_whatweb_parses_ansi_output_and_stack_signals():
    from tools.wrappers import whatweb

    raw = (
        "\x1b[1m\x1b[34mhttps://wksagency.com\x1b[0m [200 OK] "
        "\x1b[1mCloudFlare\x1b[0m, "
        "\x1b[1mCountry\x1b[0m[\x1b[0m\x1b[22mUNITED STATES\x1b[0m], "
        "\x1b[1mHTML5\x1b[0m, "
        "\x1b[1mHTTPServer\x1b[0m[\x1b[1m\x1b[36mcloudflare\x1b[0m], "
        "\x1b[1mX-Powered-By\x1b[0m[\x1b[0m\x1b[22mNext.js\x1b[0m]\n"
    )
    techs = whatweb._parse_technologies(raw)
    assert "Cloudflare" in techs
    assert "HTML5" in techs
    assert "Next.js" in techs
    assert "Cookies" not in techs
    assert "HttpOnly" not in techs
    assert "m" not in techs
    assert whatweb._parse_http_status(raw) == "200 OK"


def test_whatweb_detects_cloudflare_challenge_and_filters_noise():
    from tools.wrappers import whatweb

    raw = (
        "https://distrokid.com [403 Forbidden] "
        "Cookies[__cf_bm], Country[UNITED STATES][US], HTML5, "
        "HTTPServer[cloudflare], HttpOnly[__cf_bm], IP[104.18.18.179], Script, "
        "Title[Just a moment...], "
        "UncommonHeaders[accept-ch,cf-mitigated,content-security-policy,critical-ch,"
        "cross-origin-embedder-policy,cross-origin-opener-policy,cross-origin-resource-policy,"
        "origin-agent-cluster,permissions-policy,referrer-policy,server-timing,"
        "x-content-type-options,cf-ray], "
        "X-Frame-Options[SAMEORIGIN], X-UA-Compatible[IE=Edge]\n"
    )
    techs = whatweb._parse_technologies(raw)
    assert set(techs) == {"HTML5", "Cloudflare"}
    waf = whatweb._detect_waf_challenge(raw, "403 Forbidden")
    assert waf["waf_blocked"] is True
    assert waf["waf_vendor"] == "Cloudflare"
    assert waf["page_title"] == "Just a moment..."


def test_httpx_probe_parses_pd_output():
    from tools.wrappers import httpx_probe

    line = (
        "https://wksagency.com [200] [We Know Secrets | Digital Distribution & Marketing Agency] "
        "[Cloudflare,Next.js,Node.js,React]"
    )
    parsed = httpx_probe._parse_line(line)
    assert parsed["status_code"] == "200"
    assert "Next.js" in parsed["technologies"]
    assert parsed["title"].startswith("We Know Secrets")


def test_gobuster_parses_ansi_status_lines():
    output = (
        "\x1b[2K/careers              (Status: 200) [Size: 16974]\n"
        "\x1b[2K/default              (Status: 200) [Size: 65238]\n"
        "\x1b[2K/Default              (Status: 200) [Size: 65238]\n"
        "\x1b[2K/robots.txt           (Status: 200) [Size: 0]\n"
    )
    assert gobuster._parse_directories(output) == [
        {"path": "/careers", "status": "200", "size": "16974"},
        {"path": "/default", "status": "200", "size": "65238"},
        {"path": "/robots.txt", "status": "200", "size": "0"},
    ]


def test_gobuster_length_from_error():
    msg = (
        "Error: the server returns a status code that matches the provided options "
        "for non existing urls. https://example.com/uuid => 403 (Length: 650). "
        "To continue please exclude the status code or the length"
    )
    assert gobuster._length_from_error(msg) == 650


def test_gobuster_with_exclude_length_replaces_previous():
    args = ["dir", "-u", "https://x", "--exclude-length", "1", "-q"]
    assert gobuster._with_exclude_length(args, 650) == [
        "dir",
        "-u",
        "https://x",
        "-q",
        "--exclude-length",
        "650",
    ]


def test_rustscan_host_strips_url():
    assert rustscan._host("https://wks.agency/path") == "wks.agency"
    assert rustscan._host("wks.agency") == "wks.agency"


def test_masscan_extract_host():
    assert masscan._extract_host("https://wks.agency:443/x") == "wks.agency"


def test_masscan_parse_port_list():
    assert masscan._ports_from_args(["-p80,443,22", "--rate=1000"]) == [80, 443, 22]
    assert masscan._ports_from_args(["-p", "80,443"]) == [80, 443]
    assert masscan._ports_from_args(["-p1-3"]) == [1, 2, 3]


def test_masscan_sanitize_strips_nmap_flags_and_wide_ranges():
    cleaned = masscan.sanitize_args(["-sV", "--limit=1000", "-p1-1024"])
    assert "-sV" not in cleaned
    assert not any(a.startswith("--limit") for a in cleaned)
    ports = masscan._ports_from_args(cleaned)
    assert ports
    assert len(ports) <= masscan.MAX_FALLBACK_PORTS
    assert "--wait=0" in cleaned
    assert "--rate=1000" in cleaned


def test_masscan_sanitize_splits_glued_rate_wait_and_drops_output_json():
    cleaned = masscan.sanitize_args(
        ["-p80,443,22", "--rate=1000 --wait=0", "output=json"]
    )
    assert "output=json" not in cleaned
    assert "--rate=1000" in cleaned
    assert "--wait=0" in cleaned
    # Must be separate tokens — glued form breaks masscan rate parser.
    assert not any(" " in a for a in cleaned)
    assert masscan._ports_from_args(cleaned) == [80, 443, 22]


def test_gobuster_sanitize_requires_dir_and_maps_url_flag():
    cleaned = gobuster.sanitize_args(
        ["--url", "https://example.com", "-w", "/tmp/w.txt"],
        url="https://www.example.com",
    )
    assert cleaned[0] == "dir"
    assert "-u" in cleaned
    assert "--url" not in cleaned
    assert cleaned[cleaned.index("-u") + 1] == "https://www.example.com"
    assert "-w" in cleaned


def test_gobuster_sanitize_injects_dir_when_llm_omits_mode():
    cleaned = gobuster.sanitize_args(["-u", "https://example.com"])
    assert cleaned[0] == "dir"
    assert "-w" in cleaned
    assert cleaned[cleaned.index("-w") + 1]


def test_gobuster_rewrites_missing_seclists_wordlist(monkeypatch):
    monkeypatch.setattr(
        "tools.wrappers._wordlists.os.path.isfile",
        lambda path: path == "/usr/share/dirb/wordlists/common.txt",
    )
    cleaned = gobuster.sanitize_args(
        [
            "dir",
            "-u",
            "https://takwene.com",
            "-w",
            "/usr/share/seclists/Discovery/Web-Content/common.txt",
        ],
        url="https://takwene.com",
    )
    assert cleaned[cleaned.index("-w") + 1] == gobuster.WORDLIST
    assert "seclists" not in cleaned[cleaned.index("-w") + 1]


def test_masscan_tcp_connect_respects_budget(monkeypatch):
    calls = {"n": 0}
    times = {"t": 0.0}

    monkeypatch.setattr(masscan.time, "monotonic", lambda: times["t"])

    def advance_then_fail(*_a, **_k):
        calls["n"] += 1
        times["t"] += 10.0
        raise OSError("closed")

    monkeypatch.setattr(masscan.socket, "create_connection", advance_then_fail)
    masscan._tcp_connect_ports("1.2.3.4", list(range(1, 200)), budget_seconds=25, max_ports=200)
    # Budget 25s / 10s per attempt => at most a few probes before break
    assert calls["n"] <= 4


def test_masscan_tcp_connect_fallback(monkeypatch):
    monkeypatch.setattr(masscan, "_resolve_target", lambda host: "1.2.3.4")
    monkeypatch.setattr(
        masscan,
        "_run_masscan_syn",
        lambda *a, **k: ("", []),
    )
    monkeypatch.setattr(
        masscan,
        "_tcp_connect_ports",
        lambda address, ports, timeout=1.0, **kwargs: [
            {"port": "80", "protocol": "tcp"},
            {"port": "443", "protocol": "tcp"},
        ],
    )

    result = masscan.scan("example.com", ["-p80,443", "--rate=1000"])

    assert "error" not in result
    assert result["ports"] == [
        {"port": "80", "protocol": "tcp"},
        {"port": "443", "protocol": "tcp"},
    ]
    assert result["method"] == "tcp-connect-fallback"
    assert "fallback" in result["raw_output"].lower()


def test_masscan_prefers_syn_results(monkeypatch):
    monkeypatch.setattr(masscan, "_resolve_target", lambda host: "1.2.3.4")
    monkeypatch.setattr(
        masscan,
        "_run_masscan_syn",
        lambda *a, **k: (
            "Discovered open port 443/tcp on 1.2.3.4\n",
            [{"port": "443", "protocol": "tcp"}],
        ),
    )

    called = {"fallback": False}

    def boom(*a, **k):
        called["fallback"] = True
        return []

    monkeypatch.setattr(masscan, "_tcp_connect_ports", boom)

    result = masscan.scan("example.com", ["-p443", "--rate=1000"])

    assert called["fallback"] is False
    assert result["method"] == "syn"
    assert result["ports"] == [{"port": "443", "protocol": "tcp"}]


def test_nmap_sqlmap_nuclei_ffuf_url_helpers():
    assert nmap._host("https://wks.agency/x") == "wks.agency"
    assert sqlmap._url("wks.agency") == "https://wks.agency"
    assert nuclei._url("wks.agency") == "https://wks.agency"
    assert ffuf._url("wks.agency") == "https://wks.agency"


def test_hydra_default_args_target_only(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)

        class Result:
            returncode = 0
            stdout = "[DATA] attacking ssh://lab.example:22/\n"
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(hydra, "_default_wordlist", lambda: "/tmp/passes.txt")
    monkeypatch.setattr(hydra, "_tcp_reachable", lambda *a, **k: True)
    monkeypatch.setattr(hydra, "_ssh_banner_valid", lambda *a, **k: True)

    result = hydra.scan("lab.example")

    assert "error" not in result
    assert result["service"] == "ssh"
    assert calls[0][:3] == ["hydra", "-l", "admin"]
    assert calls[0][-2:] == ["lab.example", "ssh"]
    assert "-P" in calls[0]


def test_hydra_builds_command_with_normalized_target(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)

        class Result:
            returncode = 0
            stdout = "Hydra finished"
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(hydra, "_tcp_reachable", lambda *a, **k: True)
    monkeypatch.setattr(hydra, "_ssh_banner_valid", lambda *a, **k: True)

    result = hydra.scan(
        "ssh://lab.example:22",
        ["ssh", "-l", "operator", "-P", "/tmp/lab-passwords.txt", "-t", "1"],
    )

    assert calls == [
        [
            "hydra",
            "-W",
            "3",
            "-l",
            "operator",
            "-P",
            "/tmp/lab-passwords.txt",
            "-t",
            "1",
            "lab.example",
            "ssh",
        ]
    ]
    assert result["raw_output"] == "Hydra finished"
    assert "error" not in result


def test_hydra_accepts_native_service_url_args(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(hydra, "_tcp_reachable", lambda *a, **k: True)
    monkeypatch.setattr(hydra, "_ssh_banner_valid", lambda *a, **k: True)

    result = hydra.scan(
        "takwene.com",
        ["-l", "admin", "-P", "/tmp/passes.txt", "ssh://takwene.com"],
    )

    assert calls[0] == [
        "hydra",
        "-W",
        "3",
        "-l",
        "admin",
        "-P",
        "/tmp/passes.txt",
        "ssh://takwene.com",
    ]
    assert result["service"] == "ssh"


def test_hydra_skips_when_ssh_filtered(monkeypatch):
    called = []

    def fake_run(command, **kwargs):
        called.append(command)

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(hydra, "_tcp_reachable", lambda *a, **k: False)
    monkeypatch.setattr(hydra, "_ssh_banner_valid", lambda *a, **k: True)

    result = hydra.scan(
        "www.cdn.example",
        ["-l", "admin", "-P", "/tmp/passes.txt", "ssh://www.cdn.example"],
    )

    assert result.get("skipped") is True
    assert called == []
    assert "not reachable" in result["raw_output"].lower()


def test_hydra_reports_missing_binary(monkeypatch):
    def missing_binary(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing_binary)
    monkeypatch.setattr(hydra, "_tcp_reachable", lambda *a, **k: True)
    monkeypatch.setattr(hydra, "_ssh_banner_valid", lambda *a, **k: True)

    result = hydra.scan("lab.example", ["ssh", "-l", "operator", "-p", "test"])

    assert result["error"] == "hydra binary not found"


def test_zmap_host_and_ports():
    from tools.wrappers import zmap

    assert zmap._host("https://takwene.com/x") == "takwene.com"
    assert zmap._ports_from_args(["-p", "80,443"]) == [80, 443]


def test_nikto_and_xsstrike_url_helpers(monkeypatch):
    from tools.wrappers import nikto, xsstrike
    from tools.wrappers._web_url import ensure_https_url

    # Avoid live DNS/HTTP probes; wrappers bind canonicalize at import time.
    monkeypatch.setattr(nikto, "canonicalize_web_url", ensure_https_url)
    monkeypatch.setattr(xsstrike, "canonicalize_web_url", ensure_https_url)

    assert nikto._url("takwene.com") == "https://takwene.com"
    assert xsstrike._url("takwene.com").startswith("https://takwene.com")
    assert "?q=test" in xsstrike._url("takwene.com")


def test_xsstrike_headers_use_escaped_newlines():
    from tools.wrappers import xsstrike

    encoded = xsstrike._headers_arg(
        {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        }
    )
    assert "\\n" in encoded
    assert "," not in encoded.split("\\n")[0] or encoded.startswith("User-Agent:")
    assert "Accept: text/html,application/xhtml+xml,*/*;q=0.8" in encoded


def test_xsstrike_normalize_args_adds_timeout_skip_and_safe_headers():
    from tools.wrappers import xsstrike

    args = xsstrike._normalize_args(["--threads", "3"], {"random_headers": True})
    assert "--timeout" in args
    assert args[args.index("--timeout") + 1] == "20"
    assert "--skip" in args
    assert "--headers" in args
    header_blob = args[args.index("--headers") + 1]
    assert "\\n" in header_blob
    assert "User-Agent:" in header_blob


def test_xsstrike_parse_findings_strips_ansi():
    from tools.wrappers import xsstrike

    output = (
        "\x1b[91m[-]\x1b[0m WAF detected: ASP.NET\n"
        "\x1b[93m[!]\x1b[0m Reflections found: 1\n"
        "[-] No vectors were crafted.\n"
    )
    findings = xsstrike._parse_findings(output)
    assert any("WAF detected" in f for f in findings)
    assert any("Reflections found" in f for f in findings)
    assert any("No vectors were crafted" in f for f in findings)

def test_impacket_and_cme_host_helpers():
    from tools.wrappers import impacket, crackmapexec

    assert impacket._host("smb://lab.example/share") == "lab.example"
    assert crackmapexec._host("https://lab.example") == "lab.example"


def test_rustscan_ensures_address_after_flag():
    assert rustscan._ensure_address(["-a", "--ulimit", "5000"], "takwene.com") == [
        "-a",
        "takwene.com",
        "--ulimit",
        "5000",
    ]
    assert rustscan._ensure_address(["--ulimit", "5000", "--top"], "takwene.com") == [
        "-a",
        "takwene.com",
        "--ulimit",
        "5000",
        "--top",
    ]


def test_rustscan_parses_open_host_port_lines():
    output = "Open 34.72.42.51:80\nOpen 34.72.42.51:443\nOpen 34.72.42.51:22\n"
    assert rustscan._parse_ports(output) == [
        {"port": "80", "state": "open"},
        {"port": "443", "state": "open"},
        {"port": "22", "state": "open"},
    ]


def test_ffuf_parses_status_lines_with_spaces():
    output = (
        "Documents and Settings  [Status: 301, Size: 168, Words: 11, Lines: 2]\n"
        "\x1b[2KProgram Files           [Status: 301, Size: 159, Words: 10, Lines: 2]\n"
        "\x1b[2K                        [Status: 200, Size: 65306, Words: 27760, Lines: 979]\n"
        "\x1b[2Kcareers                 [Status: 200, Size: 17049, Words: 5297, Lines: 278]\n"
    )
    assert ffuf._parse_results(output) == [
        {"path": "Documents and Settings", "status": "301", "size": "168"},
        {"path": "Program Files", "status": "301", "size": "159"},
        {"path": "/", "status": "200", "size": "65306"},
        {"path": "careers", "status": "200", "size": "17049"},
    ]


def test_nikto_drops_port_when_url_host_used():
    from tools.wrappers import nikto

    assert nikto._normalize_args(
        "https://takwene.com",
        ["-ssl", "-port", "443", "-maxtime", "60"],
    ) == ["-maxtime", "60"]


def test_hydra_normalizes_nested_target_url():
    host, service, command = hydra._build_command(
        "https://takwene.com",
        ["-l", "admin", "-P", "/tmp/pass.txt", "ssh://https://takwene.com"],
    )
    assert host == "takwene.com"
    assert service == "ssh"
    assert command[-1] == "ssh://takwene.com"


def test_gobuster_status_from_error_and_blacklist():
    msg = (
        "Error: the server returns a status code that matches the provided options "
        "for non existing urls. https://example.com/uuid => 301 (Length: 182). "
        "To continue please exclude the status code or the length"
    )
    assert gobuster._status_from_error(msg) == "301"
    assert gobuster._with_blacklist_status(["dir", "-u", "https://x", "-b", "404"], "301") == [
        "dir",
        "-u",
        "https://x",
        "-b",
        "301,404",
    ]


def test_nuclei_rewrites_llm_template_alias(tmp_path, monkeypatch):
    root = tmp_path / "nuclei-templates"
    (root / "http" / "cves").mkdir(parents=True)
    monkeypatch.setattr(nuclei, "TEMPLATE_ROOTS", (str(root),))
    args = nuclei._normalize_args(["-template", "cves/", "-severity", "high"])
    assert args[0] == "-t"
    assert "cves" in args[1]


def test_ffuf_expands_glued_wordlist_token():
    glued = "-w /dev/shm/words.txt http://takwene.com HTTP/1.1"
    args = ffuf._normalize_args([glued, "-u", "https://x/FUZZ"], "https://www.takwene.com")
    assert "-w" in args
    w = args[args.index("-w") + 1]
    assert "HTTP/" not in w
    assert "://" not in w
    assert args[args.index("-u") + 1].startswith("https://")


def test_nmap_sanitizes_illegal_port_specs():
    cleaned = nmap.sanitize_args(["-sV", "-p", "https://evil/80", "-T4"])
    assert cleaned[cleaned.index("-p") + 1].replace(",", "").replace("-", "").isdigit() or all(
        c.isdigit() or c in ",-T:U" for c in cleaned[cleaned.index("-p") + 1]
    )
    glued = nmap.sanitize_args(["-p80 443 bad"])
    assert "-p" in glued[1] or glued[1].startswith("-p") or "80" in "".join(glued)


def test_hydra_injects_login_when_missing():
    _host, _svc, cmd = hydra._build_command("www.example.com", ["ssh"])
    assert "-l" in cmd or "-L" in cmd or "-C" in cmd
    assert "-P" in cmd or "-p" in cmd



def test_hydra_skips_default_ssh_without_banner(monkeypatch):
    monkeypatch.setattr(hydra, "_ssh_banner_valid", lambda *_a, **_k: False)
    result = hydra.scan("takwene.com")
    assert result.get("skipped") is True
    assert "SSH banner" in (result.get("raw_output") or "")


def test_hydra_skips_default_ssh_on_https_target():
    result = hydra.scan("https://takwene.com")
    assert result.get("skipped") is True
    assert "HTTP(S)" in (result.get("raw_output") or "")


def test_whatweb_normalizes_timeouts_and_parses_technologies():
    from tools.wrappers import whatweb

    args = whatweb._normalize_args(["-a", "3"])
    assert "--open-timeout" in args
    assert "--read-timeout" in args
    output = "https://wksagency.com [200 OK] Apache[2.4.41], PHP[7.4], Bootstrap[4.3]"
    assert whatweb._parse_technologies(output) == ["Apache", "PHP", "Bootstrap"]


def test_ffuf_rewrites_common_wordlist_aliases():
    args = ffuf._normalize_args(
        ["-u", "http://takwene.com/FUZZ", "-w", "/usr/share/wordlists/dirb/common.txt"],
        "https://www.takwene.com",
    )
    assert args[args.index("-u") + 1] == "https://www.takwene.com/FUZZ"
    assert args[args.index("-w") + 1] == "/usr/share/dirb/wordlists/common.txt"
    assert "-ac" in args


def test_sqlmap_flags_crawl_without_injection_tests():
    from tools.wrappers import sqlmap

    output = (
        "[10:25:18] [INFO] starting crawler for target URL 'https://distrokid.com'\n"
        "[10:25:18] [INFO] searching for links with depth 1\n"
        "[10:25:18] [INFO] searching for links with depth 2\n"
        "[10:25:18] [INFO] searching for links with depth 3\n"
        "do you want to normalize crawling results [Y/n] Y\n"
    )
    flags = sqlmap._analyze_sqlmap_output(output, vulnerable=False)
    assert flags["no_injection_surface"] is True
    assert flags["partial"] is True
    assert "never reached an injectable parameter" in str(flags["note"]).lower()


def test_sqlmap_flags_no_injection_surface_from_output():
    from tools.wrappers import sqlmap

    output = (
        "[10:23:23] [INFO] starting crawler for target URL 'https://distrokid.com'\n"
        "[10:23:23] [WARNING] no usable links found (with GET parameters) or forms\n"
    )
    flags = sqlmap._analyze_sqlmap_output(output, vulnerable=False)
    assert flags["no_injection_surface"] is True
    assert flags["partial"] is True
    assert "inconclusive" in str(flags["note"]).lower()


def test_ffuf_custom_args_receive_a_runtime_limit():
    args = ffuf._normalize_args(
        ["-u", "{{target}}/FUZZ", "-w", "/tmp/words.txt"],
        "https://takwene.com",
    )
    maxtime = int(args[args.index("-maxtime") + 1])
    assert maxtime >= 60


def test_ffuf_runtime_budget_scales_with_wordlist(tmp_path):
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("\n".join(f"w{i}" for i in range(200)), encoding="utf-8")
    args = ffuf._normalize_args(
        ["-u", "{{target}}/FUZZ", "-w", str(wordlist), "-maxtime", "30"],
        "https://takwene.com",
    )
    assert int(args[args.index("-maxtime") + 1]) >= 60


def test_ffuf_cdn_backoff_drops_autocalibrate_under_stealth():
    args = ffuf._normalize_args(
        ["-u", "{{target}}/FUZZ", "-w", "/tmp/words.txt", "-ac", "-t", "40"],
        "https://takwene.com",
        evasion={"random_headers": True, "random_delay_min": 1.0},
    )
    assert "-ac" not in args
    assert args[args.index("-t") + 1] == "5"
    assert args[args.index("-rate") + 1] == "8"
    assert int(args[args.index("-maxtime") + 1]) >= 60


def test_ffuf_detects_cdn_stall_output():
    stalled = (
        ":: Progress: [40/4614] :: Job [1/1] :: 0 req/sec :: Duration: [0:00:20] :: Errors: 40 ::\n"
        "[WARN] Maximum running time for entire process reached, exiting.\n"
    )
    assert ffuf._looks_like_cdn_stall(stalled) is True
    assert ffuf._looks_like_cdn_stall(":: Progress: [100/100] :: 50 req/sec :: Errors: 0 ::") is False
    # Early 0 req/sec is normal; do not flag a run that later made progress.
    progressed = (
        ":: Progress: [5/4614] :: Job [1/1] :: 0 req/sec :: Duration: [0:00:00] :: Errors: 0 ::\n"
        ":: Progress: [800/4614] :: Job [1/1] :: 8 req/sec :: Duration: [0:00:45] :: Errors: 2 ::\n"
        "[WARN] Maximum running time for entire process reached, exiting.\n"
    )
    assert ffuf._looks_like_cdn_stall(progressed) is False


def test_ffuf_preserves_url_and_session_cookie_with_cdn_backoff():
    url = ffuf._url("wks.agency")
    args = [
        "-u",
        "https://wks.agency/FUZZ",
        "-w",
        "/usr/share/dirb/wordlists/common.txt",
        "-mc",
        "200,301,302",
        "-H",
        "Cookie: XSRF-TOKEN=abc123; laravel_session=xyz",
    ]
    norm = ffuf._normalize_args(args, url, evasion={"random_headers": True})
    assert "-u" in norm
    u_index = norm.index("-u")
    assert norm[u_index + 1] == "https://wks.agency/FUZZ"
    cookie_pairs = [
        (norm[i], norm[i + 1])
        for i in range(len(norm) - 1)
        if norm[i] in {"-H", "--header"}
    ]
    assert any("cookie:" in value.lower() for _, value in cookie_pairs)
    assert "XSRF-TOKEN=abc123" not in [a for a in norm if not a.startswith("-")]


def test_crackmapexec_strips_url_target_args():
    from tools.wrappers import crackmapexec

    assert crackmapexec._normalize_args(
        ["smb", "https://takwene.com", "-u", "admin", "-p", "password"],
        "takwene.com",
    ) == ["smb", "takwene.com", "-u", "admin", "-p", "password"]
