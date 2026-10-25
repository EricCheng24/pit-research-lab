"""Historical Phase A pins and explicit B01 current pins are separate checks."""

import subprocess
from hashlib import sha256

FROZEN = "6edf54d4b81b7047c632937112aa4d764aa806b6"
# Filled from the settled, authorized changed files; never derived during a test.
CURRENT_PINS = {
    ".github/workflows/ci.yml": (
        4817,
        "506dc6de1ef7d935241b82e9a4638092ac20cfdaa5aa75accf30727e7b25dabb",
    ),
    "src/pit_research_lab/domain/contracts.py": (
        24933,
        "d0a15387c919cdeafa7fc166952f9878487ae0337ec4ff92327b4c9ceb0a3bac",
    ),
    "src/pit_research_lab/domain/information.py": (
        42942,
        "fc1ed60a5fb3066553a18322f69df195429f7e83bd6dba774cb201d0f5c216d7",
    ),
    "src/pit_research_lab/domain/temporal.py": (
        18274,
        "09dfd6108c5ba2e117fb61ab4b9ce9254d342d1bf26fcfbf16d221b1d3f25dc7",
    ),
    "tests/unit/cap_f2_v1_a03/a03_inputs.py": (
        14423,
        "591d718692f7766082263a6374ee2d29b9e6bf0dcb02b5869a154563937eb7d3",
    ),
    "tests/unit/cap_f2_v1_a03/test_asof_slice.py": (
        28336,
        "20e35eaf454eb6758aa73097dbfe41c7996badb2343707608da9f608ac00be1b",
    ),
    "tests/unit/cap_f2_v1_a04/test_derived_slice.py": (
        23969,
        "c06dfc62f8cd9f2fee96ed204bb54184439658966fbd02bc4f3db879f3eb5c6c",
    ),
    "tests/unit/cap_f2_v1_a05/test_ratio_slice.py": (
        28162,
        "0d566f0e154a19fb2d18b93238b74c061de217d6c7545b9bf70f8b14449138ce",
    ),
    "tests/unit/cap_f2_v1_a06_ic3_rs2/test_issuer_html_extraction.py": (
        34877,
        "9acc55546cefd60188da16d06122a6eb4e956bb4c96b45c31915c684fb476c3d",
    ),
    "tests/unit/cap_f2_v1_a06_ic3_rs3f/test_sec_real_closure.py": (
        20120,
        "b76885a84560e49c0d4ab384f99ceff768487f754c0657d5985abb111861b409",
    ),
    "tests/unit/cap_f2_wu01/test_s1_s2_contract_hardening.py": (
        20897,
        "9f554fc05fde257aecbe742a69be6eb99e6abd336418150a74c7dddbe4613f85",
    ),
    "tests/unit/cap_f2_wu01/test_wu01_information.py": (
        48452,
        "63c6146654003f266f3b99d10b9fc391df050bd98313e6f1a134e7628bdc64f6",
    ),
    "tests/unit/cap_f2_wu01/wu01_actual.py": (
        18524,
        "506486817411ef2abef9110ad58d43f47703b63a6c87ed036bff2452dd22cdc3",
    ),
    "tests/unit/cap_f2_wu01/wu01_inputs.py": (
        33538,
        "95de5f0217e7b3defeb06d0cc762b6f90518f7b5b81a55793ca4f8bb1a191ba3",
    ),
    "tests/unit/cap_f2_wu01c/test_pit_slice.py": (
        14060,
        "c28bce9f919453e21070e9dac05467742da6990f98242dd130ceb70d4f07ec2b",
    ),
    "tests/unit/cap_f2_wu01c/test_temporal_expansion.py": (
        21497,
        "5232d6205a514f7b54564f12b845300d70042383358f0b9e983eea9f2b702bcd",
    ),
}


def verify_preserved(root, path, length, digest):
    source = root / path
    assert root in source.parents and source.resolve() == source and source.is_file()
    live = source.read_bytes()
    if path in CURRENT_PINS:
        historical = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "show", FROZEN + ":" + path],
            capture_output=True,
            check=False,
        )
        assert historical.returncode == 0, (
            "FROZEN_HISTORY_UNAVAILABLE: checkout requires full history"
        )
        body = historical.stdout
        assert (len(live), sha256(live).hexdigest()) == CURRENT_PINS[path], (
            "B01_CURRENT_PIN_MISMATCH"
        )
    else:
        body = live
    assert (len(body), sha256(body).hexdigest()) == (length, digest), "PHASE_A_PIN_MISMATCH"
