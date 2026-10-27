"""Literal B02 baseline bytes and outer observations; no historical repinning."""

import ast
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest

from pit_research_lab.domain.causal_derivation import B03_CODE_PATHS
from pit_research_lab.domain.causal_slice import observe_causal_code

ROOT = Path(__file__).resolve().parents[3]
BASE = "1dbba5480517d94d5977284347fae6b8bbea3436"
BASELINE = {
    ".github/workflows/ci.yml": (
        4817,
        "506dc6de1ef7d935241b82e9a4638092ac20cfdaa5aa75accf30727e7b25dabb",
    ),
    "Makefile": (1239, "bb1da79acec7db3c185255e4c5264506a5ee038928446caf9943a28d20c6eb5d"),
    "pyproject.toml": (936, "9b8d98b71f96c1b33663ae76fe8889439d74cf54181f3084333540cf83e1c819"),
    "src/pit_research_lab/__init__.py": (
        79,
        "8121e022e7de092b4c79651137a4ccd89cd450ba910d65bb507b15781a52a5ff",
    ),
    "src/pit_research_lab/domain/__init__.py": (
        0,
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ),
    "src/pit_research_lab/domain/asof_slice.py": (
        3055,
        "5500f53b0526b2e629ec844cef99b9445479900fc3e73ba98c9e48e2d30b2a31",
    ),
    "src/pit_research_lab/domain/contracts.py": (
        24933,
        "d0a15387c919cdeafa7fc166952f9878487ae0337ec4ff92327b4c9ceb0a3bac",
    ),
    "src/pit_research_lab/domain/derivation.py": (
        17339,
        "bd52a33d8f971adbd11f12ad7ec7c905fd2c6404ac40d1674c303a16e97534e9",
    ),
    "src/pit_research_lab/domain/derived_slice.py": (
        1681,
        "26976c30bfb45cd70d012f4242bd5cad44811b63786ce2f403dd9d1c825873bb",
    ),
    "src/pit_research_lab/domain/financial_semantics.py": (
        25102,
        "df447297f91404f9bd1431de1d709d14b36f60e3c473993cd6f3b16050a4a960",
    ),
    "src/pit_research_lab/domain/financial_semantics_slice.py": (
        7424,
        "8ef6a0318cc56bb23dd9af31a19fa05d9cdf3ecc367535885345ccf63c767813",
    ),
    "src/pit_research_lab/domain/information.py": (
        42942,
        "fc1ed60a5fb3066553a18322f69df195429f7e83bd6dba774cb201d0f5c216d7",
    ),
    "src/pit_research_lab/domain/issuer_html_extraction.py": (
        29798,
        "f6cdc70564b4836543f732dfaed630e1f0a563986e88145f748a7e8d7d0e9cd3",
    ),
    "src/pit_research_lab/domain/issuer_html_slice.py": (
        10438,
        "4930e8635729b5d7d92cf4202595575f1e2edd2b19d3512996beb3386411b425",
    ),
    "src/pit_research_lab/domain/market_row_selection.py": (
        12199,
        "2167b7649fd5b6051c924af146839eecdaee6e31bf8948d7d28b1d82b57440af",
    ),
    "src/pit_research_lab/domain/market_source_slice.py": (
        13810,
        "75d5311c199f971feacf03bb4d7dca06cbc2203322a927ff5d397f807466b4e7",
    ),
    "src/pit_research_lab/domain/offline_replay.py": (
        11165,
        "d6c84c3a647bacd06e6dc06cc57f3139219b07742e766c67f6910be5fe273e7b",
    ),
    "src/pit_research_lab/domain/pit_slice.py": (
        4029,
        "ab7ba2843035811e35e66f1a22eca51bc6d1b20d07248bb4f6097a76e898cc53",
    ),
    "src/pit_research_lab/domain/ratio.py": (
        13897,
        "018953c2631bb197ff505ec1cb14ab4191b46ebfbcca4670017080e7cafd6996",
    ),
    "src/pit_research_lab/domain/ratio_slice.py": (
        1805,
        "499ba15fcbb772aac3cbb9a9b88b883a7c3b9ee506aeb15f5957d9d47e67673a",
    ),
    "src/pit_research_lab/domain/sec_financial_diagnostic.py": (
        12262,
        "8d7a7498bd4ba4504595b6532bec42ddbd78a323774fa96ba70ec74f0ded4e7e",
    ),
    "src/pit_research_lab/domain/sec_real_closure.py": (
        16090,
        "71d505eef87dfd7635997fed2929cb4f4571b842505912fa0544183bf856cfd8",
    ),
    "src/pit_research_lab/domain/selection.py": (
        63295,
        "15ab6df10542df799a54a41e716c19fd13f52e3c738fba6e689b649c171f0202",
    ),
    "src/pit_research_lab/domain/source_adapter.py": (
        12770,
        "afaec82a33bded42b567f0d1bd2305d5a823f5b965e87ca6494747fb1108c4df",
    ),
    "src/pit_research_lab/domain/source_intake.py": (
        17278,
        "c59235802a73f3285e98fbff72d5faa97e8797324bcbcf3f5e3b8cf60e48a240",
    ),
    "src/pit_research_lab/domain/temporal.py": (
        18274,
        "09dfd6108c5ba2e117fb61ab4b9ce9254d342d1bf26fcfbf16d221b1d3f25dc7",
    ),
    "tests/unit/cap_f2_v1_a03/a03_inputs.py": (
        20021,
        "ae6449e61cfea72bfad3ed1dc94909cd3e902d4305ccbcebc408f3d3ca4d7cf8",
    ),
    "tests/unit/cap_f2_v1_a03/conftest.py": (
        199,
        "46834d480522ceb96af9c04d972401e131e1ccf99cfe91e7eccdf243e1c27f2f",
    ),
    "tests/unit/cap_f2_v1_a03/test_asof_slice.py": (
        28336,
        "20e35eaf454eb6758aa73097dbfe41c7996badb2343707608da9f608ac00be1b",
    ),
    "tests/unit/cap_f2_v1_a03/test_b02_relations_asof.py": (
        64769,
        "db1a96649718a3d357051201e0ae7d937e0049b2f5aea7f76f844dd8c052fe5d",
    ),
    "tests/unit/cap_f2_v1_a04/a04_inputs.py": (
        8646,
        "80fb6bd80bd287f3fd03a9f8839bb246f1e8ab8d02dc9db2f58b3a55bd71d89f",
    ),
    "tests/unit/cap_f2_v1_a04/conftest.py": (
        238,
        "937337ec3dc1ce039cdcd39824f82e2f9952df1557a692c7efd78e4f31f6c25d",
    ),
    "tests/unit/cap_f2_v1_a04/test_derived_slice.py": (
        23969,
        "c06dfc62f8cd9f2fee96ed204bb54184439658966fbd02bc4f3db879f3eb5c6c",
    ),
    "tests/unit/cap_f2_v1_a05/a05_inputs.py": (
        1803,
        "4eb32f3a21ff7be86a94674e1255502e8bfc3cc87fddc3ef871ff86043dc2e14",
    ),
    "tests/unit/cap_f2_v1_a05/conftest.py": (
        257,
        "08dc5933e867193072e0c18a7d8c7a6b71cd3c4f0b3a130b36abff67bae59395",
    ),
    "tests/unit/cap_f2_v1_a05/test_ratio_slice.py": (
        28162,
        "0d566f0e154a19fb2d18b93238b74c061de217d6c7545b9bf70f8b14449138ce",
    ),
    "tests/unit/cap_f2_v1_a06_ic1/conftest.py": (
        310,
        "88ec1ee6cd345174349415de67e30527e345161490eb0ca29c69fb983d39792c",
    ),
    "tests/unit/cap_f2_v1_a06_ic1/ic1_inputs.py": (
        5999,
        "90b7b7c259acf75701da2f33248ca20c0e598fa7a60e14be239e2ae95ad89189",
    ),
    "tests/unit/cap_f2_v1_a06_ic1/test_market_source_slice.py": (
        23817,
        "b8357c4323445363cab4cec1fb960ccc02cc883ffa774c9a096d54339cbce1cf",
    ),
    "tests/unit/cap_f2_v1_a06_ic3_rs2/b01_preservation.py": (
        5024,
        "33f3439bfd931a85ae2944a233eda6a8a6bfa0fd8a1573e4cd8fd906d2b938ac",
    ),
    "tests/unit/cap_f2_v1_a06_ic3_rs2/conftest.py": (
        318,
        "1bc869afe3823a0dd50aa5cd853af8b4d18d3e5e17a8a4a4bc8a2d7a855e0204",
    ),
    "tests/unit/cap_f2_v1_a06_ic3_rs2/rs2_inputs.py": (
        23831,
        "0967227c8884b27721db7168dfb945cc0992eb8678cbc5cca4af72d023d62d55",
    ),
    "tests/unit/cap_f2_v1_a06_ic3_rs2/test_issuer_html_extraction.py": (
        35915,
        "f295d88169ca842a9d7bedceb98c10202419d0472c1146331c6681089dce631f",
    ),
    "tests/unit/cap_f2_v1_a06_ic3_rs3f/conftest.py": (
        473,
        "3175765ac85b0883727a2bf89d4218bf7516dcc24cf97d6216b7190ce650c7c8",
    ),
    "tests/unit/cap_f2_v1_a06_ic3_rs3f/test_approved_real_sec.py": (
        10571,
        "609f7f8298d3076c38a60664c0d29859575a54ac745ee07b4a93dee44783ab4d",
    ),
    "tests/unit/cap_f2_v1_a06_ic3_rs3f/test_sec_real_closure.py": (
        20120,
        "b76885a84560e49c0d4ab384f99ceff768487f754c0657d5985abb111861b409",
    ),
    "tests/unit/cap_f2_wu00/data/inputs/base.json": (
        218289,
        "77ee371b97ac2b6e3386d94ddaec7f781c32878d6786f3d77329eb9df2ec2e02",
    ),
    "tests/unit/cap_f2_wu00/data/inputs/contexts.json": (
        5935,
        "55c78326896362e029af07c747a0d879d6c00f1c0cf2a29053396b1208c0405e",
    ),
    "tests/unit/cap_f2_wu00/data/inputs/deltas.json": (
        37937,
        "d2596076d0cac4865726584b170ff0746b55f05eebd68eb07911bc5b100b8229",
    ),
    "tests/unit/cap_f2_wu00/data/oracle/cases.json": (
        163492,
        "5e37710f5082ffb1224571c846652187a7e70e2b877e4350ca51dd805fcd810d",
    ),
    "tests/unit/cap_f2_wu00/data/oracle/reference_vectors.json": (
        3269,
        "97819a7f5da053beea7b28f093634e854827ab4bbb15c20c85b10cf0d6c0b1e4",
    ),
    "tests/unit/cap_f2_wu00/data/provenance/artifact_bindings.json": (
        25330,
        "187092e7e7fd398fd6ad22b8abbeeefac70baf25bd9ef2cb1e6717426bb49534",
    ),
    "tests/unit/cap_f2_wu00/data/sources/gate4_golden_v1.0.md": (
        66992,
        "02716d2bd4d0983ed0b8d8e22f51dc7d7e2d0c0ed1d3debc6a6e50c9e9f3f3fb",
    ),
    "tests/unit/cap_f2_wu00/data/sources/p03_case_tier_ledger_v0.1.md": (
        34753,
        "553776a9c0d2f6157894bd8b66686784276f731b8e83e8ecd49a11b2a401fe44",
    ),
    "tests/unit/cap_f2_wu00/test_wu00_boundaries.py": (
        6363,
        "769ee044fe74fae66d3bab09ab3a652290b0abed724f891cc664d1fe536b78fb",
    ),
    "tests/unit/cap_f2_wu00/test_wu00_foundation.py": (
        25089,
        "a4997e96ce92a5e13c41e60144cbee9853bb898442d40075b90479c54fd40c6a",
    ),
    "tests/unit/cap_f2_wu00/test_wu00_registry.py": (
        7360,
        "93710a28f82e6a3c73ff17e77243a8247757036e70d6f189e4c3ef31da5a393e",
    ),
    "tests/unit/cap_f2_wu00/test_wu00_vectors.py": (
        7634,
        "40af975cc625954d7307e0e84ed69abd38d76081d3c53e7cb2a2d22a2eeb05e5",
    ),
    "tests/unit/cap_f2_wu00/wu00_compare.py": (
        2834,
        "b5e0a335b59354a2e2cedb2ea03bc2b7db125428c3b933bd027a8775d2331701",
    ),
    "tests/unit/cap_f2_wu00/wu00_evidence.py": (
        3274,
        "32937f9a682997e251cd5f58f47c1d1765502868e634df3ed00c4d9a4b7df90b",
    ),
    "tests/unit/cap_f2_wu00/wu00_inputs.py": (
        19372,
        "9663de3fe9cbce3c81b2e4222006c2ae97c5056bc82134a65417894fa54065b6",
    ),
    "tests/unit/cap_f2_wu00/wu00_oracle.py": (
        5050,
        "e9486fa66160814d5629a3355db75328839a7dd215aa5d24eab32a8d905a7f52",
    ),
    "tests/unit/cap_f2_wu01/test_s1_s2_contract_hardening.py": (
        20897,
        "9f554fc05fde257aecbe742a69be6eb99e6abd336418150a74c7dddbe4613f85",
    ),
    "tests/unit/cap_f2_wu01/test_wu01_bindings.py": (
        6378,
        "d788b8372d643aba8681a821a718c9142f1ae9855562b93f939f58b46aa0d12e",
    ),
    "tests/unit/cap_f2_wu01/test_wu01_boundaries.py": (
        20946,
        "956ecf502a963d4b86306bb5954265c63b867304aa08880c8dd855617982b93b",
    ),
    "tests/unit/cap_f2_wu01/test_wu01_information.py": (
        48452,
        "63c6146654003f266f3b99d10b9fc391df050bd98313e6f1a134e7628bdc64f6",
    ),
    "tests/unit/cap_f2_wu01/wu01_acceptance.py": (
        3027,
        "d53761eb7305977b31f5c6bf66c5f79849efee9fa530e88daa37e768fbf240bc",
    ),
    "tests/unit/cap_f2_wu01/wu01_actual.py": (
        18524,
        "506486817411ef2abef9110ad58d43f47703b63a6c87ed036bff2452dd22cdc3",
    ),
    "tests/unit/cap_f2_wu01/wu01_bindings.py": (
        7490,
        "f347358c615bf4b567240f4daad8af98ab6e0d80b4bfa3ca51cca1cab64fb670",
    ),
    "tests/unit/cap_f2_wu01/wu01_inputs.py": (
        33538,
        "95de5f0217e7b3defeb06d0cc762b6f90518f7b5b81a55793ca4f8bb1a191ba3",
    ),
    "tests/unit/cap_f2_wu01c/conftest.py": (
        198,
        "11e890cd346fe04b53b0011f274ff0f64202eebd819126e847b171b0bf2fd8a4",
    ),
    "tests/unit/cap_f2_wu01c/test_pit_slice.py": (
        14060,
        "c28bce9f919453e21070e9dac05467742da6990f98242dd130ceb70d4f07ec2b",
    ),
    "tests/unit/cap_f2_wu01c/test_temporal_expansion.py": (
        21497,
        "5232d6205a514f7b54564f12b845300d70042383358f0b9e983eea9f2b702bcd",
    ),
    "uv.lock": (51855, "6e209693269166357c042375f340b9428eb533c95259f93ca0f7f30ba9a4d7a3"),
}


def verify_bytes(path, expected):
    body = path.read_bytes()
    assert (len(body), sha256(body).hexdigest()) == expected, "BASELINE_PIN_MISMATCH"


def historical(root, ref, path):
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), "show", ref + ":" + path],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, "FROZEN_HISTORY_UNAVAILABLE"
    return result.stdout


def test_literal_original_baseline_and_frozen_objects():
    for path, expected in BASELINE.items():
        verify_bytes(ROOT / path, expected)
        body = historical(ROOT, BASE, path)
        assert (len(body), sha256(body).hexdigest()) == expected
    for name in ("derivation.py", "derived_slice.py", "ratio.py", "ratio_slice.py"):
        path = "src/pit_research_lab/domain/" + name
        body = historical(ROOT, "6edf54d4b81b7047c632937112aa4d764aa806b6", path)
        assert (len(body), sha256(body).hexdigest()) == BASELINE[path]


def test_baseline_tamper_and_missing_history_are_failures(tmp_path):
    path = tmp_path / "synthetic.py"
    path.write_bytes(b"original")
    expected = (8, "0682c5f2076f099c34cfdd15a9e063849ed437a49677e6fcc5b4198c76575be5")
    # Own temporary fixture: independently retained bytes, not current-file self-pinning.
    expected = (8, sha256(b"original").hexdigest())
    verify_bytes(path, expected)
    path.write_bytes(b"tampered")
    with pytest.raises(AssertionError, match="BASELINE_PIN_MISMATCH"):
        verify_bytes(path, expected)
    with pytest.raises(AssertionError, match="FROZEN_HISTORY_UNAVAILABLE"):
        historical(ROOT, "0" * 40, "src/pit_research_lab/domain/derivation.py")


def test_exact_ten_plus_two_and_outer_three_observation():
    code = observe_causal_code(ROOT)
    assert len(code.upstream_ratio.upstream_a04.observed_working_files) == 10
    assert len(code.upstream_ratio.extension_pins) == 2
    assert tuple(p.path for p in code.extension_pins) == B03_CODE_PATHS
    assert len(code.extension_byte_lengths) == 3
    for pin, length in zip(code.extension_pins, code.extension_byte_lengths, strict=True):
        body = (ROOT / pin.path).read_bytes()
        assert sha256(body).hexdigest() == pin.sha256 and len(body) == length


def test_no_trusted_consumer_or_oracle_database_dependency():
    forbidden_names = {"to_agent_observation", "publish", "export", "AgentObservation"}
    for path in B03_CODE_PATHS:
        tree = ast.parse((ROOT / path).read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                assert node.name not in forbidden_names
            if isinstance(node, ast.ImportFrom):
                assert not any(
                    word in (node.module or "")
                    for word in (
                        "oracle",
                        "wu00",
                        "sqlalchemy",
                        "psycopg",
                        "cli",
                    )
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "asdict"
    controller = (ROOT / "src/pit_research_lab/domain/sec_real_closure.py").read_text()
    assert "CODE_PROFILE_PIN_MISMATCH" in controller
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "IC1_APPROVED_REAL" not in workflow and "RS3F_APPROVED_REAL" not in workflow
