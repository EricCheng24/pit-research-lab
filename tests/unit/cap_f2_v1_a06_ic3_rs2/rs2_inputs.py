"""SYNTHETIC_TEST_ONLY invented HTML, identities, amounts and approval descriptions."""

import json
from dataclasses import replace
from hashlib import sha256

from pit_research_lab.domain.issuer_html_extraction import BW_PROFILE, SEC_PROFILE, HtmlProfileSpec
from pit_research_lab.domain.source_intake import FilePin


def pin(name, body):
    return FilePin(name, len(body), sha256(body).hexdigest())


def row(values, cell="td", attrs=""):
    return "<tr>" + "".join(f"<{cell}{attrs}>{v}</{cell}>" for v in values) + "</tr>"


def sec_spec(**changes):
    return replace(
        HtmlProfileSpec(
            SEC_PROFILE,
            "windows-1252",
            "SYNTHETIC_ISSUER",
            "SYNTHETIC_TEST_ONLY",
            "SYNTHETIC_TEST_ONLY Signal Foundry",
            "2026-09",
            "October 6, 2026",
            "8,642",
        ),
        **changes,
    )


def sec_html(**changes):
    values = {
        "issuer": "SYNTHETIC_TEST_ONLY Signal Foundry",
        "date": "October 6, 2026",
        "period": "SYNTHETIC_TEST_ONLY period notice for the period of September 2026.",
        "unit": "1) Sales volume (NT$ Thousand)",
        "amount": "8,642",
        "comparison": "5,103",
        "ytd": "73,615",
    }
    values.update(changes)
    header = row(["Period", "Items", "2026", "2025", "Changes", "%"])
    target = row(
        ["September", "Net sales", values["amount"], values["comparison"], "3,539", "69.35%"]
    )
    cumulative = row(["Year-to-Date", "Net sales", values["ytd"], "62,108", "11,507", "18.53%"])
    table = (
        '<table id="sales"><tbody>'
        + row([""] * 6)
        + header
        + target
        + cumulative
        + "</tbody></table>"
    )
    derivatives = (
        '<table id="derivatives"><tbody>'
        + row(["Financial instruments", values["amount"]])
        + "</tbody></table>"
    )
    return (
        '<!DOCTYPE html><html><head><meta charset="windows-1252"></head><body>'
        '<div id="irrelevant"><p>Exhibit 99.1</p><p>SYNTHETIC_TEST_ONLY machinery</p>'
        + table
        + "</div>"
        '<div id="revenue"><p>Exhibit 99.2</p><p>'
        + values["issuer"]
        + "</p><p>"
        + values["date"]
        + "</p>"
        "<p>"
        + values["period"]
        + "</p><div>"
        + values["unit"]
        + "</div>"
        + table
        + "<p>SYNTHETIC_TEST_ONLY Owner’s note</p>"
        + derivatives
        + "</div><script>/* SYNTHETIC_TEST_ONLY decoy: Exhibit 99.2, 8,642 */</script></body></html>"
    )


def bw_spec(**changes):
    return replace(
        HtmlProfileSpec(
            BW_PROFILE,
            "UTF-8",
            "SYNTHETIC_ISSUER",
            "SYNTHETIC_TEST_ONLY",
            "SYNTHETIC_TEST_ONLY Lantern Circuits",
            "2031-05",
            "June 4, 2031",
            "7,319",
        ),
        **changes,
    )


def bw_html():
    table = (
        "<table><tbody>"
        + row(["Monthly revenue: May 2031"], attrs=' colspan="5"')
        + row(["Period", "2031", "2030", "Y/Y Change", "Y/Y (%)"])
        + row(["May", "7,319", "6,208", "1,111", "17.90%"])
        + row(["Year-to-Date", "36,804", "29,501", "7,303", "24.76%"])
        + row(["Synthetic scale: NTD thousands."], attrs=' colspan="5"')
        + row(["Synthetic scope: consolidated."], attrs=' colspan="5"')
        + "</tbody></table>"
    )
    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body><main>'
        '<div id="bw-release-story"><p>SYNTHETIC_TEST_ONLY Lantern Circuits | May 2031 | unaudited monthly sales</p>'
        "<p>June 4, 2031</p>"
        + table
        + "</div><aside><h2>SYNTHETIC_TEST_ONLY April 2031 unrelated</h2>"
        + table
        + "</aside>"
        '</main><script>const decoy = "SYNTHETIC_TEST_ONLY 7,319";</script></body></html>'
    )


def material(text=None, spec=None, name="synthetic.html"):
    spec = sec_spec() if spec is None else spec
    text = (sec_html() if spec.profile_id == SEC_PROFILE else bw_html()) if text is None else text
    body = text.encode("cp1252" if spec.declared_encoding == "windows-1252" else "utf-8")
    return body, pin(name, body), spec


def rights_description(pin, spec, code, **updates):
    data = {
        "description_schema": "RS2-RIGHTS-DESCRIPTION-PROPOSED-v0.1",
        "source_pin": {
            "relative_path": pin.relative_path,
            "byte_length": pin.byte_length,
            "sha256": pin.sha256,
        },
        "profile_id": spec.profile_id,
        "profile_version": spec.profile_version,
        "source_role": spec.source_role,
        "reference_month": spec.reference_month,
        "issuer_name": spec.issuer_name,
        "code_pins": [{"path": p.path, "sha256": p.sha256} for p in code],
        "terms_pin": None,
        "decision_pin": None,
        "approval_ref": None,
        "declared_status": "PENDING_REVIEW",
    }
    data.update(updates)
    return json.dumps(data).encode()


def write_source(root, body, name="synthetic.html"):
    root.mkdir()
    (root / name).write_bytes(body)
    return pin(name, body)


CANDIDATE_PINS = (
    (
        "src/pit_research_lab/domain/__init__.py",
        0,
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ),
    (
        "src/pit_research_lab/domain/asof_slice.py",
        4281,
        "316de07468f68ad44631639dad1e541f1d89e4aeb4f9d5ac613752e2fbbdc3d9",
    ),
    (
        "src/pit_research_lab/domain/contracts.py",
        23287,
        "ea4b630f6482badb0ba69b697f1903bd7f778d32cac1269e194fa50563b7c82f",
    ),
    (
        "src/pit_research_lab/domain/derivation.py",
        17339,
        "bd52a33d8f971adbd11f12ad7ec7c905fd2c6404ac40d1674c303a16e97534e9",
    ),
    (
        "src/pit_research_lab/domain/derived_slice.py",
        1681,
        "26976c30bfb45cd70d012f4242bd5cad44811b63786ce2f403dd9d1c825873bb",
    ),
    (
        "src/pit_research_lab/domain/financial_semantics.py",
        25102,
        "df447297f91404f9bd1431de1d709d14b36f60e3c473993cd6f3b16050a4a960",
    ),
    (
        "src/pit_research_lab/domain/financial_semantics_slice.py",
        7424,
        "8ef6a0318cc56bb23dd9af31a19fa05d9cdf3ecc367535885345ccf63c767813",
    ),
    (
        "src/pit_research_lab/domain/information.py",
        39920,
        "1734f1e6f5adefa7253765a15066f91c8076f588d5a6457a046b5c3fb366513b",
    ),
    (
        "src/pit_research_lab/domain/market_row_selection.py",
        12199,
        "2167b7649fd5b6051c924af146839eecdaee6e31bf8948d7d28b1d82b57440af",
    ),
    (
        "src/pit_research_lab/domain/market_source_slice.py",
        13810,
        "75d5311c199f971feacf03bb4d7dca06cbc2203322a927ff5d397f807466b4e7",
    ),
    (
        "src/pit_research_lab/domain/offline_replay.py",
        11165,
        "d6c84c3a647bacd06e6dc06cc57f3139219b07742e766c67f6910be5fe273e7b",
    ),
    (
        "src/pit_research_lab/domain/pit_slice.py",
        4029,
        "ab7ba2843035811e35e66f1a22eca51bc6d1b20d07248bb4f6097a76e898cc53",
    ),
    (
        "src/pit_research_lab/domain/ratio.py",
        13897,
        "018953c2631bb197ff505ec1cb14ab4191b46ebfbcca4670017080e7cafd6996",
    ),
    (
        "src/pit_research_lab/domain/ratio_slice.py",
        1805,
        "499ba15fcbb772aac3cbb9a9b88b883a7c3b9ee506aeb15f5957d9d47e67673a",
    ),
    (
        "src/pit_research_lab/domain/selection.py",
        27375,
        "c4bece6867e6213da543734b8d43c38a29a8b2cceb47f78f1e1d243df5f8b42b",
    ),
    (
        "src/pit_research_lab/domain/source_adapter.py",
        12770,
        "afaec82a33bded42b567f0d1bd2305d5a823f5b965e87ca6494747fb1108c4df",
    ),
    (
        "src/pit_research_lab/domain/source_intake.py",
        17278,
        "c59235802a73f3285e98fbff72d5faa97e8797324bcbcf3f5e3b8cf60e48a240",
    ),
    (
        "src/pit_research_lab/domain/temporal.py",
        17115,
        "0470cb3a9fc4b85044add1ced2e142fdc4e3f42dffaaef9fc042f2015a004c63",
    ),
    (
        "tests/unit/cap_f2_v1_a03/a03_inputs.py",
        14066,
        "49abe404faf795f6712b3453db8124d13424833c103cb98d87a6794a551973be",
    ),
    (
        "tests/unit/cap_f2_v1_a03/conftest.py",
        199,
        "46834d480522ceb96af9c04d972401e131e1ccf99cfe91e7eccdf243e1c27f2f",
    ),
    (
        "tests/unit/cap_f2_v1_a03/test_asof_slice.py",
        28250,
        "7b05c3df48c4aea37d635717fca0acddf6d8fe638eb5682e2968706d9bdef68c",
    ),
    (
        "tests/unit/cap_f2_v1_a04/a04_inputs.py",
        8646,
        "80fb6bd80bd287f3fd03a9f8839bb246f1e8ab8d02dc9db2f58b3a55bd71d89f",
    ),
    (
        "tests/unit/cap_f2_v1_a04/conftest.py",
        238,
        "937337ec3dc1ce039cdcd39824f82e2f9952df1557a692c7efd78e4f31f6c25d",
    ),
    (
        "tests/unit/cap_f2_v1_a04/test_derived_slice.py",
        24070,
        "d100486313bd5364912f943836a4ca6ec017631823a21d4b1064753686c824bc",
    ),
    (
        "tests/unit/cap_f2_v1_a05/a05_inputs.py",
        1803,
        "4eb32f3a21ff7be86a94674e1255502e8bfc3cc87fddc3ef871ff86043dc2e14",
    ),
    (
        "tests/unit/cap_f2_v1_a05/conftest.py",
        257,
        "08dc5933e867193072e0c18a7d8c7a6b71cd3c4f0b3a130b36abff67bae59395",
    ),
    (
        "tests/unit/cap_f2_v1_a05/test_ratio_slice.py",
        28092,
        "277cb9567b8d56f44904282f18734f369099f6f9882a16002523682954be756e",
    ),
    (
        "tests/unit/cap_f2_v1_a06/a06_inputs.py",
        5369,
        "917a8f0dd7b70711fe1194fc3edab1311a29b9819335cc885d0c45e01a28ad3f",
    ),
    (
        "tests/unit/cap_f2_v1_a06/conftest.py",
        264,
        "c0d31c3fb03812daa8711d1fb87c37fb8fe17c8db170cf74dfd7c7456f7a8291",
    ),
    (
        "tests/unit/cap_f2_v1_a06/test_offline_source.py",
        22352,
        "1c58a1af8c6b100bbe523bfac1965d6be10572b29edf5794f3c63f1ffd56fe97",
    ),
    (
        "tests/unit/cap_f2_v1_a06_ic1/conftest.py",
        310,
        "88ec1ee6cd345174349415de67e30527e345161490eb0ca29c69fb983d39792c",
    ),
    (
        "tests/unit/cap_f2_v1_a06_ic1/ic1_inputs.py",
        5999,
        "90b7b7c259acf75701da2f33248ca20c0e598fa7a60e14be239e2ae95ad89189",
    ),
    (
        "tests/unit/cap_f2_v1_a06_ic1/test_market_source_slice.py",
        23778,
        "cedcd2ecd13edb87934fb5a99023eac2ffae01cbc52583b75aa8a22dd355b288",
    ),
    (
        "tests/unit/cap_f2_v1_a06_ic3/conftest.py",
        322,
        "da8e957220b7d562c26ffb230e1546e18c34628d50b2e09f522d6a8d28ed3694",
    ),
    (
        "tests/unit/cap_f2_v1_a06_ic3/ic3_inputs.py",
        7391,
        "e6898a8eb1ca5c0775cd573bef0cba02052bd376deafaf2b6f901d279bd10e4c",
    ),
    (
        "tests/unit/cap_f2_v1_a06_ic3/test_financial_semantics.py",
        26668,
        "6d7307ccc36ee237b7c99e4d78f9013141c730fda62704368a630b1ec3f12685",
    ),
    (
        "tests/unit/cap_f2_wu01/test_wu01_bindings.py",
        6378,
        "d788b8372d643aba8681a821a718c9142f1ae9855562b93f939f58b46aa0d12e",
    ),
    (
        "tests/unit/cap_f2_wu01/test_wu01_boundaries.py",
        20946,
        "956ecf502a963d4b86306bb5954265c63b867304aa08880c8dd855617982b93b",
    ),
    (
        "tests/unit/cap_f2_wu01/test_wu01_information.py",
        48452,
        "7bef7b0bd50893ed0990d75199ad2b4a94a14c5520bac68cdc779691dd3d56a6",
    ),
    (
        "tests/unit/cap_f2_wu01/wu01_acceptance.py",
        3027,
        "d53761eb7305977b31f5c6bf66c5f79849efee9fa530e88daa37e768fbf240bc",
    ),
    (
        "tests/unit/cap_f2_wu01/wu01_actual.py",
        16596,
        "32b172383d5e93e7cac94bfc86812bcb39a15b2bb7000198eb83951740d73147",
    ),
    (
        "tests/unit/cap_f2_wu01/wu01_bindings.py",
        7490,
        "f347358c615bf4b567240f4daad8af98ab6e0d80b4bfa3ca51cca1cab64fb670",
    ),
    (
        "tests/unit/cap_f2_wu01/wu01_inputs.py",
        31771,
        "fae877f34cf0f4b44eb23796c9e7212c07caefb8ba6dddd14e76808001043281",
    ),
    (
        "tests/unit/cap_f2_wu01c/conftest.py",
        198,
        "11e890cd346fe04b53b0011f274ff0f64202eebd819126e847b171b0bf2fd8a4",
    ),
    (
        "tests/unit/cap_f2_wu01c/test_pit_slice.py",
        14147,
        "8def1054f978540903d64bc81356fcc48be1194c5655d13e6c809134d2163a8b",
    ),
    (
        "tests/unit/cap_f2_wu01c/test_temporal_expansion.py",
        21212,
        "139126728e09104cbf1827ed6cff1985bacacd89681a65371a9014418102f8df",
    ),
)


TRACKED_PINS = (
    (".env.example", 706, "48634a7075c1c7a787fd82a1a23dbcf09dbe47a348de2321d11c26dd59ef0f19"),
    (".gitattributes", 253, "56253e402ecacc48fece9ed57985364a877fad9da3b09aa3de7a04ec5258b15e"),
    (
        ".github/pull_request_template.md",
        327,
        "48a123a918b74eb28b84a69ee4d423091b58cb25b30a9d95ab4b4a6205a3c6cb",
    ),
    (
        ".github/workflows/ci.yml",
        4767,
        "beefd15f925fb7cf68dfd5c2e7ee204da1e3692579c975b36d62662d7eaa9bbc",
    ),
    (".gitignore", 673, "ac79f0cd4739b7ffa2fece97614c6a02bc1cb3377aa033513376cbb88cd79b7f"),
    (".python-version", 5, "7b55f8e67b5623c4bef3fa691288da9437d79d3aba156de48d481db32ac7d16d"),
    ("Makefile", 1239, "bb1da79acec7db3c185255e4c5264506a5ee038928446caf9943a28d20c6eb5d"),
    ("README.md", 8664, "161e59d9cc0561fdcf0133b4b2637630e14eec22a9c628d0f21d5c209d83472f"),
    ("alembic.ini", 100, "8965c450bfd77867a3b02b26c5a0cfce35002fbba0f57fd2cd25aa0009393d70"),
    ("compose.dev.yaml", 1744, "a13b52414e7f6109498cfb58a1acff96918714eda9b02f22c9a9d925258e3a3e"),
    ("compose.test.yaml", 1756, "5a23f07ebc95f9eff1589ce5144b95ff28ac7a750b7af9f22657082d51f17da4"),
    (
        "docs/architecture/overview.md",
        1423,
        "97e81e512e160b0f58d5ea541c6281d05a2a6af67e1ead77c7afadd2a88867b5",
    ),
    (
        "docs/development/cap-f1-3-remediation-1.md",
        9055,
        "1b20f52be7b0346b016d9fe46906d0b38cbf9d0cb2f3c7fba6b1f3de3658222b",
    ),
    (
        "docs/development/contributing.md",
        7180,
        "9059d03790d71c6597bed1bf5c7e8d77da47ffea9e3b087285523f13d5d38260",
    ),
    (
        "docs/development/database.md",
        18612,
        "f4f00c04174ccd8baf66c32f6891dad4d93ea8ea60ffbc46e5f4e42393dc82c6",
    ),
    (
        "docs/development/environment-doctor.md",
        9695,
        "81611112efd66c38508926d44b219b2b981308aff70199ae21449a05b5846761",
    ),
    (
        "docs/development/onboarding-macos-arm64.md",
        5475,
        "57c4799526fa9421f057d1da588cb8eda5f589db4efe68a03afa302972244614",
    ),
    (
        "docs/development/onboarding-wsl2.md",
        5358,
        "05c38e616f553cca41914be5e74d9f19dc913bac3d37991784330a76828bda4f",
    ),
    (
        "docs/development/onboarding.md",
        14023,
        "b03b291f4758174c9387659fb22cc1c47bf3ccac2ff8aaacfdab9b1075525dab",
    ),
    (
        "docs/development/platform-support.md",
        8150,
        "7f2706c67608f49f7781de0acfc544eaa609695f96eccc7c6449a7f1baec6fca",
    ),
    (
        "docs/development/testing.md",
        5965,
        "7b73dfba4cb6fd8bf9e5cb215e154e5c65b00a1fe697fa98d7257a917554113b",
    ),
    ("migrations/env.py", 2487, "2007d6ef12e605ab6ba974a310788a6711b61d77369701d07ff54741fd8c660b"),
    (
        "migrations/script.py.mako",
        502,
        "4edbbe38e0d613c65a259d4612dfe417e875ae56baae11be52d42e99c352508c",
    ),
    (
        "migrations/versions/f13_empty_baseline.py",
        223,
        "1767b94927a7591ae9ac28addd5074e7d31b452a320264291593a215200957d9",
    ),
    ("pyproject.toml", 936, "9b8d98b71f96c1b33663ae76fe8889439d74cf54181f3084333540cf83e1c819"),
    (
        "scripts/database.py",
        30012,
        "9116dacbe90fd489b35b99c9261b9f2e6408e8ee7944cbfbedfb8a207d99ce76",
    ),
    ("scripts/doctor.sh", 1795, "cc759c5ea62b73fae20a88a3d161347e95304a98fee846094225f0adfa4922a9"),
    (
        "scripts/environment_doctor.py",
        21075,
        "46e11c3fe484cf91b65b9c35e7449ce83fa0a6849bb2cc34acf2807518c0af0f",
    ),
    (
        "scripts/init-postgres.sh",
        1773,
        "2b8bb32bba7820db0b4e11c2e8c40d24477ffde62fb9933751033d4b900a8aeb",
    ),
    (
        "src/pit_research_lab/__init__.py",
        79,
        "8121e022e7de092b4c79651137a4ccd89cd450ba910d65bb507b15781a52a5ff",
    ),
    (
        "src/pit_research_lab/cli.py",
        410,
        "59c483acaeefe063dc9e2804c8e002edc9eab0e204b51a2ad8d71f1895ecbe87",
    ),
    (
        "src/pit_research_lab/infrastructure/__init__.py",
        65,
        "1a81b8ac635f68fbd0be2facf427303438a813404cd17f4fed49fe16b4cbc6c1",
    ),
    (
        "src/pit_research_lab/infrastructure/database/__init__.py",
        64,
        "02db7ef622b6620d8519ccec297df0be81dc3f2fdd1b048f4208534c8e2c1410",
    ),
    (
        "src/pit_research_lab/infrastructure/database/config.py",
        6369,
        "a55b7c7257fe85c53d7dc2431444df1dad1e23e41be75c74699012cbdb215e00",
    ),
    (
        "src/pit_research_lab/infrastructure/database/engine.py",
        5947,
        "8baf204e000e442ede8bfc2fef245c29fcd0eceb8ee19ffe2bfc39d7914db6cd",
    ),
    (
        "tests/integration/database/conftest.py",
        2070,
        "eae097ed6bcbd51cf0c1257dd1651a83e1724b8265b5e21b237d106d30dd0e83",
    ),
    (
        "tests/integration/database/test_connection.py",
        2992,
        "ea330bf61dcf13e238de29e8fe3d666d643a6dc4f79bd2751502cae2071b4564",
    ),
    (
        "tests/integration/database/test_migrations.py",
        3139,
        "dfcac0f50978db91d8d98836909a3f411a2e6be717248d425f00481925741947",
    ),
    (
        "tests/integration/database/test_transactions.py",
        1632,
        "52f96f84db9d4480f061b7fd6723a5199f3f356b895b5c07fe058f359d614029",
    ),
    (
        "tests/unit/cap_f2_wu00/data/inputs/base.json",
        218289,
        "77ee371b97ac2b6e3386d94ddaec7f781c32878d6786f3d77329eb9df2ec2e02",
    ),
    (
        "tests/unit/cap_f2_wu00/data/inputs/contexts.json",
        5935,
        "55c78326896362e029af07c747a0d879d6c00f1c0cf2a29053396b1208c0405e",
    ),
    (
        "tests/unit/cap_f2_wu00/data/inputs/deltas.json",
        37937,
        "d2596076d0cac4865726584b170ff0746b55f05eebd68eb07911bc5b100b8229",
    ),
    (
        "tests/unit/cap_f2_wu00/data/oracle/cases.json",
        163492,
        "5e37710f5082ffb1224571c846652187a7e70e2b877e4350ca51dd805fcd810d",
    ),
    (
        "tests/unit/cap_f2_wu00/data/oracle/reference_vectors.json",
        3269,
        "97819a7f5da053beea7b28f093634e854827ab4bbb15c20c85b10cf0d6c0b1e4",
    ),
    (
        "tests/unit/cap_f2_wu00/data/provenance/artifact_bindings.json",
        25330,
        "187092e7e7fd398fd6ad22b8abbeeefac70baf25bd9ef2cb1e6717426bb49534",
    ),
    (
        "tests/unit/cap_f2_wu00/data/sources/gate4_golden_v1.0.md",
        66992,
        "02716d2bd4d0983ed0b8d8e22f51dc7d7e2d0c0ed1d3debc6a6e50c9e9f3f3fb",
    ),
    (
        "tests/unit/cap_f2_wu00/data/sources/p03_case_tier_ledger_v0.1.md",
        34753,
        "553776a9c0d2f6157894bd8b66686784276f731b8e83e8ecd49a11b2a401fe44",
    ),
    (
        "tests/unit/cap_f2_wu00/test_wu00_boundaries.py",
        6363,
        "769ee044fe74fae66d3bab09ab3a652290b0abed724f891cc664d1fe536b78fb",
    ),
    (
        "tests/unit/cap_f2_wu00/test_wu00_foundation.py",
        25089,
        "a4997e96ce92a5e13c41e60144cbee9853bb898442d40075b90479c54fd40c6a",
    ),
    (
        "tests/unit/cap_f2_wu00/test_wu00_registry.py",
        7360,
        "93710a28f82e6a3c73ff17e77243a8247757036e70d6f189e4c3ef31da5a393e",
    ),
    (
        "tests/unit/cap_f2_wu00/test_wu00_vectors.py",
        7634,
        "40af975cc625954d7307e0e84ed69abd38d76081d3c53e7cb2a2d22a2eeb05e5",
    ),
    (
        "tests/unit/cap_f2_wu00/wu00_compare.py",
        2834,
        "b5e0a335b59354a2e2cedb2ea03bc2b7db125428c3b933bd027a8775d2331701",
    ),
    (
        "tests/unit/cap_f2_wu00/wu00_evidence.py",
        3274,
        "32937f9a682997e251cd5f58f47c1d1765502868e634df3ed00c4d9a4b7df90b",
    ),
    (
        "tests/unit/cap_f2_wu00/wu00_inputs.py",
        19372,
        "9663de3fe9cbce3c81b2e4222006c2ae97c5056bc82134a65417894fa54065b6",
    ),
    (
        "tests/unit/cap_f2_wu00/wu00_oracle.py",
        5050,
        "e9486fa66160814d5629a3355db75328839a7dd215aa5d24eab32a8d905a7f52",
    ),
    (
        "tests/unit/test_cli_smoke.py",
        1522,
        "4f69905663e2fdf0c6d162ec5d5ba69d80eb15f4934b4219d356f57473793d4e",
    ),
    (
        "tests/unit/test_database_bind_mounts.py",
        22276,
        "e8f73da3a97ade2f3fd833c97765571469babcd2c2a76108622390bbc96d7a8d",
    ),
    (
        "tests/unit/test_database_config.py",
        4203,
        "b0c806d1bcb9686ccbe9172adf905be60099666469564c8ff96bc10aecc61734",
    ),
    (
        "tests/unit/test_database_engine.py",
        6772,
        "12391a40ad29690ebb6dce5c9c5ff50c4ec4432972242dafbe16e474e50abaff",
    ),
    (
        "tests/unit/test_database_safety.py",
        18046,
        "79c5ff51cfbc5336a058b154b6449b9c7ce55139506f7c014fb701a59c93dc4a",
    ),
    (
        "tests/unit/test_environment_doctor.py",
        32968,
        "d39c09b2d47dd3380cc76dcdad9184c5bdd632ae8eeec546507c2c123d4b44e4",
    ),
    (
        "tests/unit/test_package_smoke.py",
        638,
        "794e3ffab8f5456ddceef9f6089f971303d3c29ffbca10fc7a75b04ba339b80e",
    ),
    ("uv.lock", 51855, "6e209693269166357c042375f340b9428eb533c95259f93ca0f7f30ba9a4d7a3"),
)


WU00_PINS = (
    (
        "tests/unit/cap_f2_wu00/data/inputs/base.json",
        218289,
        "77ee371b97ac2b6e3386d94ddaec7f781c32878d6786f3d77329eb9df2ec2e02",
    ),
    (
        "tests/unit/cap_f2_wu00/data/inputs/contexts.json",
        5935,
        "55c78326896362e029af07c747a0d879d6c00f1c0cf2a29053396b1208c0405e",
    ),
    (
        "tests/unit/cap_f2_wu00/data/inputs/deltas.json",
        37937,
        "d2596076d0cac4865726584b170ff0746b55f05eebd68eb07911bc5b100b8229",
    ),
    (
        "tests/unit/cap_f2_wu00/data/oracle/cases.json",
        163492,
        "5e37710f5082ffb1224571c846652187a7e70e2b877e4350ca51dd805fcd810d",
    ),
    (
        "tests/unit/cap_f2_wu00/data/oracle/reference_vectors.json",
        3269,
        "97819a7f5da053beea7b28f093634e854827ab4bbb15c20c85b10cf0d6c0b1e4",
    ),
    (
        "tests/unit/cap_f2_wu00/data/sources/gate4_golden_v1.0.md",
        66992,
        "02716d2bd4d0983ed0b8d8e22f51dc7d7e2d0c0ed1d3debc6a6e50c9e9f3f3fb",
    ),
    (
        "tests/unit/cap_f2_wu00/data/sources/p03_case_tier_ledger_v0.1.md",
        34753,
        "553776a9c0d2f6157894bd8b66686784276f731b8e83e8ecd49a11b2a401fe44",
    ),
    (
        "tests/unit/cap_f2_wu00/test_wu00_boundaries.py",
        6363,
        "769ee044fe74fae66d3bab09ab3a652290b0abed724f891cc664d1fe536b78fb",
    ),
    (
        "tests/unit/cap_f2_wu00/test_wu00_foundation.py",
        25089,
        "a4997e96ce92a5e13c41e60144cbee9853bb898442d40075b90479c54fd40c6a",
    ),
    (
        "tests/unit/cap_f2_wu00/test_wu00_registry.py",
        7360,
        "93710a28f82e6a3c73ff17e77243a8247757036e70d6f189e4c3ef31da5a393e",
    ),
    (
        "tests/unit/cap_f2_wu00/test_wu00_vectors.py",
        7634,
        "40af975cc625954d7307e0e84ed69abd38d76081d3c53e7cb2a2d22a2eeb05e5",
    ),
    (
        "tests/unit/cap_f2_wu00/wu00_compare.py",
        2834,
        "b5e0a335b59354a2e2cedb2ea03bc2b7db125428c3b933bd027a8775d2331701",
    ),
    (
        "tests/unit/cap_f2_wu00/wu00_evidence.py",
        3274,
        "32937f9a682997e251cd5f58f47c1d1765502868e634df3ed00c4d9a4b7df90b",
    ),
    (
        "tests/unit/cap_f2_wu00/wu00_inputs.py",
        19372,
        "9663de3fe9cbce3c81b2e4222006c2ae97c5056bc82134a65417894fa54065b6",
    ),
    (
        "tests/unit/cap_f2_wu00/wu00_oracle.py",
        5050,
        "e9486fa66160814d5629a3355db75328839a7dd215aa5d24eab32a8d905a7f52",
    ),
)
