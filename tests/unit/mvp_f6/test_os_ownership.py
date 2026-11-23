"""U01–U04: supplied facts only; live entrypoints are trapped and refuse."""

import ast
import socket
import struct
from dataclasses import fields, replace
from pathlib import Path

import pytest

from pit_research_lab.mvp.f6 import contracts as c
from pit_research_lab.mvp.f6.backend import os_ownership as o
from pit_research_lab.mvp.f6.backend.launch_policy import ModelError

IDS = tuple(f"71000000-0000-4000-8000-{n:012d}" for n in range(1, 10))


def claim():
    return o.ProcessClaim(
        IDS[0],
        IDS[1],
        IDS[2],
        IDS[3],
        4001,
        4000,
        "101",
        4001,
        4001,
        "a" * 64,
        "8",
        "9",
        "8",
        "10",
        "b" * 64,
        "c" * 64,
        "d" * 64,
        "e" * 64,
    )


def test_supplied_identity_fences_all_fields():
    expected = claim()
    assert o.same_supplied_identity(expected, expected)
    for field in fields(expected):
        value = getattr(expected, field.name)
        if field.name in ("installation_id", "generation", "launcher_id", "boot_id"):
            changed = IDS[8]
        elif type(value) is int:
            changed = value + 1
        elif field.name.endswith("sha256"):
            changed = "f" * 64
        else:
            changed = str(int(value) + 1)
        assert not o.same_supplied_identity(expected, replace(expected, **{field.name: changed}))
    for field, value in (
        ("pid", True),
        ("parent_pid", 1),
        ("start_ticks", "01"),
        ("boot_id", "unknown"),
        ("job_ino", "0"),
    ):
        with pytest.raises((ModelError, c.ContractError)):
            replace(expected, **{field: value})
    with pytest.raises(o.PhysicalNotAuthorized):
        o.require_physical_session(expected, "launcher")


def test_channel_credentials_sequence_and_closed_frames():
    binding = o.Binding(IDS[0], IDS[4], IDS[1], IDS[2], "a" * 64)
    sender = o.Credentials(4001, 1000, 1000)
    creds = ((socket.SOL_SOCKET, socket.SCM_CREDENTIALS, struct.pack("3i", 4001, 1000, 1000)),)
    payload = {"permission_id": IDS[5], "revision": 3, "event_sha256": "b" * 64}
    first = o.frame(binding, 1, "GO", payload)
    window = o.ChannelWindow(binding, sender)
    assert window.accept(first, creds)["payload"] == payload
    with pytest.raises(ModelError):
        window.accept(first, creds)
    assert window.closed and window.accepted == 1
    vectors = [
        (first, (), 0),
        (first, creds + creds, 0),
        (first, creds, socket.MSG_TRUNC),
        (first, ((socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack("i", 9)),), 0),
        (first, ((socket.SOL_SOCKET, socket.SCM_CREDENTIALS, b"bad"),), 0),
        (
            first,
            ((socket.SOL_SOCKET, socket.SCM_CREDENTIALS, struct.pack("3i", 4002, 1000, 1000)),),
            0,
        ),
        (first.replace(IDS[1].encode(), IDS[8].encode()), creds, 0),
        (first.replace(b'"nonce":"a', b'"nonce":"b'), creds, 0),
        (b"x" * 16385, creds, 0),
        (first.replace(b'"revision":3', b'"revision":true'), creds, 0),
        (first.replace(b'"version":1', b'"version":true'), creds, 0),
        (first.replace(b'"GO"', b'"RESUME"'), creds, 0),
    ]
    for raw, ancillary, flags in vectors:
        fresh = o.ChannelWindow(binding, sender)
        with pytest.raises((ModelError, c.ContractError)):
            fresh.accept(raw, ancillary, flags)
        assert fresh.closed and fresh.accepted == 0
    bounded = o.ChannelWindow(binding, sender)
    for n in range(1, 33):
        bounded.accept(o.frame(binding, n, "GO", payload), creds)
    with pytest.raises(ModelError):
        bounded.accept(first, creds)
    with pytest.raises(ModelError):
        o.frame(binding, 1, "GO", {**payload, "extra": 1})


def channel_facts():
    binding = o.Binding(IDS[0], IDS[4], IDS[1], IDS[2], "a" * 64)
    sender = o.Credentials(4001, 1000, 1000)
    control = (socket.SOL_SOCKET, socket.SCM_CREDENTIALS, struct.pack("3i", 4001, 1000, 1000))
    payload = {"permission_id": IDS[5], "revision": 3, "event_sha256": "b" * 64}
    return binding, sender, control, payload


@pytest.mark.parametrize("container", [list, tuple], ids=["native-list", "recorded-tuple"])
def test_native_ancillary_list_and_tuple_accept(container):
    binding, sender, control, payload = channel_facts()
    window = o.ChannelWindow(binding, sender)
    for sequence in (1, 2):
        assert (
            window.accept(o.frame(binding, sequence, "GO", payload), container([control]))[
                "payload"
            ]
            == payload
        )
        assert window.accepted == sequence and not window.closed
    # This proves supplied-fact parsing only, never kernel credential provenance.
    with pytest.raises(o.PhysicalNotAuthorized):
        o.require_physical_session(window, "launcher")


def bad_ancillary_cases():
    _, _, control, _ = channel_facts()
    level, kind, data = control
    return [
        pytest.param([], id="empty"),
        pytest.param([control, control], id="duplicate-credentials"),
        pytest.param([(level, socket.SCM_RIGHTS, struct.pack("i", 9))], id="rights"),
        pytest.param([control, (level, socket.SCM_RIGHTS, b"")], id="extra-rights"),
        pytest.param([(-1, kind, data)], id="wrong-level"),
        pytest.param([(level, -1, data)], id="wrong-type"),
        pytest.param([(level, kind + 1000, data)], id="unknown-control"),
        pytest.param([(True, kind, data)], id="boolean-level"),
        pytest.param([(level, True, data)], id="boolean-type"),
        pytest.param([(str(level), kind, data)], id="string-level"),
        pytest.param([(level, str(kind), data)], id="string-type"),
        pytest.param([None], id="null-inner"),
        pytest.param([3], id="integer-inner"),
        pytest.param([list(control)], id="list-inner"),
        pytest.param([()], id="empty-inner-tuple"),
        pytest.param([(level, kind)], id="short-inner-tuple"),
        pytest.param([(*control, 0)], id="long-inner-tuple"),
        pytest.param([(level, kind, bytearray(data))], id="bytearray-data"),
        pytest.param([(level, kind, memoryview(data))], id="memoryview-data"),
        pytest.param([(level, kind, "credentials")], id="string-data"),
        pytest.param([(level, kind, None)], id="null-data"),
        pytest.param([(level, kind, data[:-1])], id="short-credentials"),
        pytest.param([(level, kind, data + b"x")], id="long-credentials"),
        pytest.param([(level, kind, struct.pack("3i", 4002, 1000, 1000))], id="wrong-pid"),
        pytest.param([(level, kind, struct.pack("3i", 4001, 1001, 1000))], id="wrong-uid"),
        pytest.param([(level, kind, struct.pack("3i", 4001, 1000, 1001))], id="wrong-gid"),
    ]


@pytest.mark.parametrize("container", [list, tuple], ids=["native-list", "recorded-tuple"])
@pytest.mark.parametrize("controls", bad_ancillary_cases())
def test_native_ancillary_malformed_shapes_close_irreversibly(container, controls):
    binding, sender, control, payload = channel_facts()
    window = o.ChannelWindow(binding, sender)
    first = o.frame(binding, 1, "GO", payload)
    with pytest.raises(ModelError):
        window.accept(first, container(controls))
    assert window.closed and window.accepted == 0
    with pytest.raises(ModelError):
        window.accept(first, [control])
    assert window.closed and window.accepted == 0


@pytest.mark.parametrize("ancillary", [None, {}, b"credentials", "credentials", 3])
def test_ancillary_noncontainers_close(ancillary):
    binding, sender, _, payload = channel_facts()
    window = o.ChannelWindow(binding, sender)
    with pytest.raises(ModelError):
        window.accept(o.frame(binding, 1, "GO", payload), ancillary)
    assert window.closed and window.accepted == 0


@pytest.mark.parametrize(
    "flags",
    [True, -1, 1 << 30]
    + [getattr(socket, name) for name in ("MSG_TRUNC", "MSG_CTRUNC") if hasattr(socket, name)],
)
def test_native_ancillary_flags_close_irreversibly(flags):
    binding, sender, control, payload = channel_facts()
    window = o.ChannelWindow(binding, sender)
    first = o.frame(binding, 1, "GO", payload)
    with pytest.raises(ModelError):
        window.accept(first, [control], flags)
    assert window.closed and window.accepted == 0
    with pytest.raises(ModelError):
        window.accept(first, [control], 0)
    assert window.closed and window.accepted == 0


def test_native_ancillary_preserves_frame_and_sequence_fences():
    binding, sender, control, payload = channel_facts()
    first = o.frame(binding, 1, "GO", payload)
    vectors = [
        first.replace(IDS[1].encode(), IDS[8].encode()),
        first.replace(b'"nonce":"a', b'"nonce":"b'),
        first.replace(b'"GO"', b'"RESUME"'),
        b"x" * (o.FRAME_LIMIT + 1),
    ]
    for raw in vectors:
        window = o.ChannelWindow(binding, sender)
        with pytest.raises(ModelError):
            window.accept(raw, [control])
        assert window.closed and window.accepted == 0
    replay = o.ChannelWindow(binding, sender)
    replay.accept(first, [control])
    with pytest.raises(ModelError):
        replay.accept(first, [control])
    assert replay.closed and replay.accepted == 1
    bounded = o.ChannelWindow(binding, sender)
    for sequence in range(1, o.FRAME_COUNT + 1):
        bounded.accept(o.frame(binding, sequence, "GO", payload), [control])
    excess = c.canonical_json({**c.decode_json(first), "sequence": o.FRAME_COUNT + 1})
    with pytest.raises(ModelError):
        bounded.accept(excess, [control])
    assert bounded.closed and bounded.accepted == o.FRAME_COUNT


def test_dormant_helper_exit_oracle_is_ast_only():
    """Inspect syntax only: no helper import, compile/eval or role invocation."""
    source = Path(__file__).resolve().parents[3] / "platform_probes/mvp_f6/_launch_helper.py"
    module = ast.parse(source.read_text(), filename=str(source))
    functions = {node.name: node for node in module.body if isinstance(node, ast.FunctionDef)}
    refusal = next(
        node.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "PROTOCOL_REFUSAL_EXIT"
            for target in node.targets
        )
    )
    assert isinstance(refusal, ast.Constant) and type(refusal.value) is int
    assert 0 <= refusal.value <= 255 and refusal.value == 70 and refusal.value not in (0, 7)

    def shape(node):
        return ast.dump(node, include_attributes=False)

    def expression(text):
        return shape(ast.parse(text, mode="eval").body)

    def refused(statements):
        assert len(statements) == 1 and isinstance(statements[0], ast.Return)
        assert shape(statements[0].value) == expression("PROTOCOL_REFUSAL_EXIT")

    child = functions["_child_body"]
    assert shape(child.body[0]) == shape(
        ast.parse('require_future_permit(session, "child")').body[0]
    )
    invalid = child.body[1]
    assert isinstance(invalid, ast.If)
    assert shape(invalid.test) == expression(
        "type(exit_code) is not int or exit_code not in (0, 7)"
    )
    refused(invalid.body)
    choices = [
        keyword.value
        for node in ast.walk(functions["parse_fixed_arguments"])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "--exit-code"
        for keyword in node.keywords
        if keyword.arg == "choices"
    ]
    assert len(choices) == 1 and ast.literal_eval(choices[0]) == (0, 7)
    protocol = next(node for node in child.body if isinstance(node, ast.Try))
    assert isinstance(protocol.body[-1], ast.Return)
    assert shape(protocol.body[-1].value) == expression("exit_code")
    guards = [node for node in protocol.body if isinstance(node, ast.If)]
    for guard in guards:
        refused(guard.body)
        assert not guard.orelse
    # Required rejection categories occur before the sole intentional return.
    conditions = {shape(guard.test) for guard in guards}
    for condition in (
        'context["type"] != "CHILD_CONTEXT" or set(context["payload"]) != '
        '{"permission_id", "child_id", "command_sha256", "deadline_monotonic_ns"}',
        'time.monotonic_ns() >= int(context["payload"]["deadline_monotonic_ns"])',
        "len(raw_stat) > 4096",
        "len(values) < 20 or int(values[1]) != parent",
        "len(encoded) > 16384 or endpoint.send(encoded) != len(encoded)",
        'release["type"] != "CHILD_REGISTERED_ACK" or set(release["payload"]) != '
        '{"child_id", "revision", "event_sha256"}',
        'release["payload"]["child_id"] != context["payload"]["child_id"]',
        "any(release[key] != context[key] for key in "
        'envelope_keys - {"type", "sequence", "payload"})',
        "time.monotonic() >= deadline",
    ):
        assert expression(condition) in conditions
    for name, sequence in (("context", 1), ("release", 2)):
        assignment = next(
            node
            for node in protocol.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
        )
        assert shape(assignment.value) == expression(f"receive({sequence})")
    assert len(protocol.handlers) == 1
    handler = protocol.handlers[0]
    assert shape(handler.type) == expression(
        "(OSError, ValueError, KeyError, TypeError, TimeoutError)"
    )
    refused(handler.body)

    class DirectReturns(ast.NodeVisitor):
        def __init__(self):
            self.nodes = []

        def visit_FunctionDef(self, node):
            pass  # Nested receive/pairs return data, not the child exit status.

        def visit_Return(self, node):
            self.nodes.append(node)

    returns = DirectReturns()
    for statement in child.body:
        returns.visit(statement)
    assert sum(shape(node.value) == expression("exit_code") for node in returns.nodes) == 1
    assert all(
        shape(node.value) in {expression("exit_code"), expression("PROTOCOL_REFUSAL_EXIT")}
        for node in returns.nodes
    )
    # Missing ACK / receive timeout / credential/identity error raises into the
    # closed handler; do not import or execute receive to simulate a live parent.
    receive = next(
        node for node in child.body if isinstance(node, ast.FunctionDef) and node.name == "receive"
    )
    assert any(isinstance(node, ast.Raise) for node in ast.walk(receive))
    permit = functions["require_future_permit"]
    assert len(permit.body) == 1 and isinstance(permit.body[0], ast.Raise)
    main = functions["main"]
    assert shape(main.body[0]) == shape(
        ast.parse('require_future_permit(None, "entrypoint")').body[0]
    )
    assert isinstance(main.body[-1], ast.Return) and ast.literal_eval(main.body[-1].value) == 7


def test_fd_plan_requires_recorded_ofd_lineage():
    plan = o.FDPlan("launcher", (5, 6))
    assert plan.descriptors == (5, 6)
    for role, descriptors in (
        ("child", (5, 6)),
        ("launcher", (5, 5)),
        ("child", (2,)),
        ("child", (True,)),
        ("native", (5,)),
    ):
        with pytest.raises(ModelError):
            o.FDPlan(role, descriptors)
    lineage = o.InheritedLeaseClaim(5, 5, "8", "9", True, True, True)
    assert lineage.consistent_model()
    for key in ("acquired_by_original_s", "passed_by_original_s", "cloexec_restored"):
        assert not replace(lineage, **{key: False}).consistent_model()
    # Even complete supplied lineage has no physical session/lease ownership.
    with pytest.raises(o.PhysicalNotAuthorized):
        o.require_physical_session(lineage, "launcher")


def test_signal_policy_refuses_unowned_or_changed_targets(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("FORBIDDEN")
        raise AssertionError("physical operation reached")

    for module, name in (
        (o.os, "open"),
        (o.os, "pidfd_open"),
        (o.os, "kill"),
        (o.os, "killpg"),
        (o.fcntl, "flock"),
        (o.fcntl, "fcntl"),
        (o.signal, "pidfd_send_signal"),
        (o.socket, "socketpair"),
        (Path, "lstat"),
        (Path, "open"),
    ):
        monkeypatch.setattr(module, name, forbidden, raising=False)
    expected = claim()
    assert o.signal_refusal(expected, expected) == "PHYSICAL_NOT_AUTHORIZED"
    assert o.signal_refusal(expected, replace(expected, start_ticks="102")) == "FOREIGN_TARGET"
    operations = (
        lambda: o.LinuxAdapters.lock(
            object(), Path("/tmp/invalid"), Path("/tmp/invalid/job.lock"), "launcher"
        ),
        lambda: o.LinuxAdapters.restore_cloexec(expected, 5),
        lambda: o.LinuxAdapters.socketpair("a" * 64),
        lambda: o.LinuxAdapters.process(expected, 4001),
        lambda: o.LinuxAdapters.pidfd(expected, expected),
        lambda: o.LinuxAdapters.signal_one(expected, 5, expected, expected, 15),
        lambda: o.PhysicalSession(),
    )
    for operation in operations:
        with pytest.raises(o.PhysicalNotAuthorized):
            operation()
    assert calls == []
