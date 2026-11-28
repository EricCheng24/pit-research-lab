"""Create the isolated, SQL-enforced fixture foundation."""

from alembic import op

revision = "d1_001"
down_revision = None
branch_labels = None
depends_on = None

DDL = """
CREATE DOMAIN public.f4_d1_sha AS text CHECK (VALUE ~ '^[0-9a-f]{64}$');

CREATE TABLE public.f4_d1_profile (
    sha public.f4_d1_sha PRIMARY KEY,
    profile text NOT NULL UNIQUE CHECK (profile IN ('fixture-issuer-v1','fixture-revenue-v1')),
    body bytea NOT NULL CHECK (octet_length(body) BETWEEN 1 AND 8192)
);
CREATE TABLE public.f4_d1_profile_event (
    profile_sha public.f4_d1_sha NOT NULL REFERENCES public.f4_d1_profile(sha),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    action text NOT NULL CHECK (action IN ('ENABLE_FIXTURE','REVOKE_FIXTURE')),
    expires_at timestamptz,
    PRIMARY KEY (profile_sha, recorded_at),
    CHECK ((action = 'ENABLE_FIXTURE' AND expires_at > recorded_at AND expires_at IS NOT NULL)
       OR (action = 'REVOKE_FIXTURE' AND expires_at IS NULL))
);
CREATE TABLE public.f4_d1_artifact (
    sha public.f4_d1_sha PRIMARY KEY,
    size integer NOT NULL CHECK (size BETWEEN 1 AND 8388608),
    UNIQUE (sha, size)
);
CREATE TABLE public.f4_d1_attempt (
    id uuid PRIMARY KEY,
    profile_sha public.f4_d1_sha NOT NULL REFERENCES public.f4_d1_profile(sha),
    request_sha public.f4_d1_sha NOT NULL,
    input_sha public.f4_d1_sha NOT NULL,
    input_name text NOT NULL CHECK (input_name ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,63}[.]csv$'),
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    deployment text NOT NULL CHECK (deployment ~ '^pitlab:(test|dev):[a-z0-9]+:[0-9a-f-]{36}$'),
    UNIQUE (id, profile_sha),
    UNIQUE (id, profile_sha, input_sha)
);
CREATE TABLE public.f4_d1_observation (
    id uuid PRIMARY KEY,
    ordinal bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    profile_sha public.f4_d1_sha NOT NULL,
    artifact_sha public.f4_d1_sha,
    size integer,
    captured_at timestamptz,
    completed_at timestamptz NOT NULL,
    result text NOT NULL CHECK (result IN ('IMPORTED_UNQUALIFIED','REFUSED','INTERRUPTED')),
    receipt_sha public.f4_d1_sha NOT NULL UNIQUE,
    receipt bytea NOT NULL CHECK (octet_length(receipt) BETWEEN 1 AND 8192),
    projection jsonb NOT NULL CHECK (jsonb_typeof(projection) = 'array'
        AND jsonb_array_length(projection) <= 2000),
    CHECK (result = 'IMPORTED_UNQUALIFIED' OR projection = '[]'::jsonb),
    CHECK (receipt_sha = encode(sha256(
        convert_to('pitlab-f4-d1/receipt/v1','UTF8') || decode('00','hex') || receipt),'hex')),
    FOREIGN KEY (id, profile_sha) REFERENCES public.f4_d1_attempt(id, profile_sha),
    FOREIGN KEY (id, profile_sha, artifact_sha)
        REFERENCES public.f4_d1_attempt(id, profile_sha, input_sha),
    FOREIGN KEY (artifact_sha, size) REFERENCES public.f4_d1_artifact(sha, size) MATCH FULL,
    UNIQUE (id, artifact_sha),
    CHECK (
        (result = 'IMPORTED_UNQUALIFIED' AND artifact_sha IS NOT NULL
          AND captured_at IS NOT NULL AND captured_at <= completed_at)
        OR (result <> 'IMPORTED_UNQUALIFIED' AND artifact_sha IS NULL AND captured_at IS NULL)
    )
);
CREATE INDEX f4_d1_observation_artifact_idx ON public.f4_d1_observation(artifact_sha);
CREATE TABLE public.f4_d1_issuer (
    key text PRIMARY KEY CHECK (key ~ '^FIC-[A-Z]{2,12}$')
);
CREATE TABLE public.f4_d1_row_result (
    observation uuid NOT NULL,
    artifact_sha public.f4_d1_sha NOT NULL,
    row_no integer NOT NULL CHECK (row_no BETWEEN 1 AND 2000),
    status text NOT NULL CHECK (status IN ('ACCEPTED','REJECTED','OUT_OF_SCOPE')),
    reason text,
    CHECK ((status = 'ACCEPTED') = (reason IS NULL)),
    CHECK (reason IS NULL OR reason ~ '^[A-Z_]{1,64}$'),
    PRIMARY KEY (observation, row_no),
    UNIQUE (observation, row_no, status),
    FOREIGN KEY (observation, artifact_sha)
        REFERENCES public.f4_d1_observation(id, artifact_sha)
);
CREATE TABLE public.f4_d1_issuer_occurrence (
    observation uuid NOT NULL,
    row_no integer NOT NULL,
    status text GENERATED ALWAYS AS ('ACCEPTED'::text) STORED,
    issuer_key text NOT NULL REFERENCES public.f4_d1_issuer(key),
    code text NOT NULL CHECK (code IN ('0001','0002')),
    name text NOT NULL CHECK (name ~ '^Fictional [A-Za-z ]{2,48}$'),
    sector text NOT NULL CHECK (sector IN ('technology','services')),
    listed_date date NOT NULL,
    PRIMARY KEY (observation, row_no),
    FOREIGN KEY (observation, row_no, status)
        REFERENCES public.f4_d1_row_result(observation, row_no, status)
);
CREATE TABLE public.f4_d1_assertion_version (
    version_sha public.f4_d1_sha PRIMARY KEY,
    subject_sha public.f4_d1_sha NOT NULL,
    issuer_key text NOT NULL REFERENCES public.f4_d1_issuer(key),
    period_start date NOT NULL,
    period_end_exclusive date NOT NULL,
    basis text NOT NULL CHECK (basis IN ('consolidated','standalone')),
    currency text NOT NULL CHECK (currency = 'TWD'),
    unit text NOT NULL CHECK (unit IN ('TWD','TWD_THOUSANDS')),
    amount numeric,
    state text NOT NULL CHECK (state IN ('PRESENT','MISSING')),
    body bytea NOT NULL CHECK (octet_length(body) BETWEEN 1 AND 8192),
    CHECK (EXTRACT(DAY FROM period_start) = 1
        AND period_end_exclusive = (period_start + INTERVAL '1 month')::date),
    CHECK ((state = 'PRESENT') = (amount IS NOT NULL)),
    CHECK (amount IS NULL OR (abs(amount) < '1e30'::numeric AND scale(amount) <= 8)),
    CHECK (convert_from(body,'UTF8')::jsonb = jsonb_build_object(
        'subject', jsonb_build_object(
            'issuer','SYNTHETIC_F4_D1/' || issuer_key,
            'market','FICTIONAL_TWSE_STYLE','identity_namespace','SYNTHETIC_F4_D1',
            'metric','MONTHLY_OPERATING_REVENUE',
            'period_start',to_char(period_start,'YYYY-MM-DD'),
            'period_end_exclusive',to_char(period_end_exclusive,'YYYY-MM-DD'),
            'basis',basis,'currency',currency,'unit',unit),
        'value',trim_scale(amount)::text,'state',state,
        'reason',CASE WHEN state='MISSING' THEN 'DECLARED_MISSING' END,
        'semantic_version','f4-d1-canon-v1')),
    subject_body bytea NOT NULL CHECK (octet_length(subject_body) BETWEEN 1 AND 8192),
    CHECK (convert_from(subject_body,'UTF8')::jsonb = convert_from(body,'UTF8')::jsonb->'subject'),
    CHECK (subject_sha = encode(sha256(
        convert_to('pitlab-f4-d1/subject/v1','UTF8') || decode('00','hex') || subject_body),'hex')),
    CHECK (version_sha = encode(sha256(
        convert_to('pitlab-f4-d1/assertion/v1','UTF8') || decode('00','hex') || body),'hex'))
);
CREATE INDEX f4_d1_assertion_subject_idx ON public.f4_d1_assertion_version(subject_sha);
CREATE TABLE public.f4_d1_assertion_occurrence (
    observation uuid NOT NULL,
    row_no integer NOT NULL,
    status text GENERATED ALWAYS AS ('ACCEPTED'::text) STORED,
    field text NOT NULL CHECK (field = 'amount'),
    version_sha public.f4_d1_sha NOT NULL REFERENCES public.f4_d1_assertion_version(version_sha),
    report_date date NOT NULL,
    PRIMARY KEY (observation, row_no, field),
    FOREIGN KEY (observation, row_no, status)
        REFERENCES public.f4_d1_row_result(observation, row_no, status)
);
CREATE INDEX f4_d1_occurrence_version_idx ON public.f4_d1_assertion_occurrence(version_sha);
CREATE TABLE public.f4_d1_custody_event (
    id uuid PRIMARY KEY REFERENCES public.f4_d1_observation(id),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    outcome text NOT NULL CHECK (outcome IN ('PUBLISHED','NO_BYTES','RECOVERED'))
);
CREATE VIEW public.f4_d1_visible_profile AS
SELECT p.sha
FROM public.f4_d1_profile p
JOIN LATERAL (
    SELECT action, expires_at
    FROM public.f4_d1_profile_event
    WHERE profile_sha=p.sha ORDER BY recorded_at DESC LIMIT 1
) e ON true
WHERE e.action = 'ENABLE_FIXTURE' AND e.expires_at > statement_timestamp();
CREATE VIEW public.f4_d1_inventory AS
SELECT o.ordinal, o.id, p.profile, o.profile_sha, o.artifact_sha, o.size,
       o.captured_at, o.completed_at, o.result, o.receipt_sha,
       COUNT(r.row_no) FILTER (WHERE r.status = 'ACCEPTED') AS accepted,
       COUNT(r.row_no) FILTER (WHERE r.status = 'REJECTED') AS rejected,
       COUNT(r.row_no) FILTER (WHERE r.status = 'OUT_OF_SCOPE') AS excluded
FROM public.f4_d1_observation o
JOIN public.f4_d1_profile p ON p.sha = o.profile_sha
JOIN public.f4_d1_visible_profile g ON g.sha = o.profile_sha
LEFT JOIN public.f4_d1_row_result r ON r.observation = o.id
GROUP BY o.id, p.profile;
CREATE VIEW public.f4_d1_values AS
SELECT p.observation, p.row_no, p.field, v.issuer_key, v.period_start,
       v.period_end_exclusive, v.basis, v.currency, v.unit, v.amount, v.state,
       v.subject_sha, v.version_sha, p.report_date
FROM public.f4_d1_assertion_occurrence p
JOIN public.f4_d1_assertion_version v ON v.version_sha = p.version_sha
JOIN public.f4_d1_observation o ON o.id = p.observation
JOIN public.f4_d1_visible_profile g ON g.sha = o.profile_sha;
CREATE VIEW public.f4_d1_issuers AS
SELECT i.observation, i.row_no, i.issuer_key, i.code, i.name, i.sector, i.listed_date
FROM public.f4_d1_issuer_occurrence i
JOIN public.f4_d1_observation o ON o.id = i.observation
JOIN public.f4_d1_visible_profile g ON g.sha = o.profile_sha;
"""


SEAL = (
    """
    CREATE FUNCTION public.f4_d1_check_child() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog AS $$
    DECLARE expected jsonb; profile_name text; actual jsonb;
    BEGIN
        SELECT o.projection -> (NEW.row_no - 1), p.profile INTO expected, profile_name
        FROM public.f4_d1_observation o
        JOIN public.f4_d1_profile p ON o.profile_sha=p.sha
        WHERE o.id=NEW.observation;
        IF TG_TABLE_NAME='f4_d1_row_result' THEN
            expected := expected - 'issuer' - 'assertion';
            actual := jsonb_build_object('row_no',NEW.row_no,'status',NEW.status,'reason',NEW.reason);
        ELSIF TG_TABLE_NAME='f4_d1_issuer_occurrence' AND profile_name='fixture-issuer-v1' THEN
            expected := expected -> 'issuer';
            actual := jsonb_build_object('key',NEW.issuer_key,'code',NEW.code,'name',NEW.name,
                'sector',NEW.sector,'listed_date',to_char(NEW.listed_date,'YYYY-MM-DD'));
        ELSIF TG_TABLE_NAME='f4_d1_assertion_occurrence' AND profile_name='fixture-revenue-v1' THEN
            expected := expected -> 'assertion';
            actual := jsonb_build_object('field',NEW.field,'version_sha',NEW.version_sha,
                'report_date',to_char(NEW.report_date,'YYYY-MM-DD'));
        ELSE
            RAISE EXCEPTION 'D1 child profile mismatch' USING ERRCODE='23514';
        END IF;
        IF expected IS DISTINCT FROM actual THEN
            RAISE EXCEPTION 'D1 child projection mismatch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END
    $$;
    """,
    """
    CREATE FUNCTION public.f4_d1_check_completion() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog AS $$
    DECLARE accepted bigint; issuer_count bigint; assertion_count bigint; profile_name text;
            attempt_row public.f4_d1_attempt%ROWTYPE; receipt_json jsonb;
            outcome_name text; complete_count bigint;
    BEGIN
        SELECT profile INTO STRICT profile_name
        FROM public.f4_d1_profile WHERE sha=NEW.profile_sha;
        SELECT * INTO STRICT attempt_row FROM public.f4_d1_attempt WHERE id=NEW.id;
        SELECT outcome INTO outcome_name FROM public.f4_d1_custody_event WHERE id=NEW.id;
        receipt_json := convert_from(NEW.receipt,'UTF8')::jsonb;
        IF NOT (receipt_json @> jsonb_build_object(
            'attempt',NEW.id,'observation','f4d1:observation:' || NEW.id,
            'profile',profile_name,'profile_sha',NEW.profile_sha,
            'deployment',attempt_row.deployment,'request_sha',attempt_row.request_sha,
            'artifact','f4d1:artifact:sha256:' || NEW.artifact_sha,'byte_count',NEW.size,
            'result',NEW.result,'mode','SYNTHETIC_ONLY','method','FIXTURE_IMPORT',
            'publication','UNRESOLVED','history_coverage','UNRESOLVED'))
            OR NEW.completed_at < attempt_row.started_at
            OR NEW.captured_at < attempt_row.started_at
            OR (receipt_json->>'started_at')::timestamptz IS DISTINCT FROM attempt_row.started_at
            OR (receipt_json->>'completed_at')::timestamptz IS DISTINCT FROM NEW.completed_at
            OR (receipt_json->>'captured_at')::timestamptz IS DISTINCT FROM NEW.captured_at
            OR (outcome_name='NO_BYTES') IS DISTINCT FROM (NEW.artifact_sha IS NULL)
        THEN
            RAISE EXCEPTION 'D1 receipt binding mismatch' USING ERRCODE='23514';
        END IF;
        SELECT count(*) FILTER (WHERE status='ACCEPTED'), count(*) INTO accepted, complete_count
        FROM public.f4_d1_row_result WHERE observation=NEW.id;
        SELECT count(*) INTO issuer_count FROM public.f4_d1_issuer_occurrence WHERE observation=NEW.id;
        SELECT count(*) INTO assertion_count FROM public.f4_d1_assertion_occurrence WHERE observation=NEW.id;
        IF complete_count <> jsonb_array_length(NEW.projection)
            OR NOT EXISTS (SELECT 1 FROM public.f4_d1_custody_event WHERE id=NEW.id)
            OR issuer_count <> (CASE WHEN profile_name='fixture-issuer-v1' THEN accepted ELSE 0 END)
            OR assertion_count <> (CASE WHEN profile_name='fixture-revenue-v1' THEN accepted ELSE 0 END)
        THEN
            RAISE EXCEPTION 'D1 incomplete sealed observation' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END
    $$;
    """,
    *(
        f"CREATE TRIGGER f4_d1_check_child BEFORE INSERT ON public.f4_d1_{child} "
        "FOR EACH ROW EXECUTE FUNCTION public.f4_d1_check_child()"
        for child in ("row_result", "issuer_occurrence", "assertion_occurrence")
    ),
    """CREATE CONSTRAINT TRIGGER f4_d1_check_completion
       AFTER INSERT ON public.f4_d1_observation
       DEFERRABLE INITIALLY DEFERRED
       FOR EACH ROW EXECUTE FUNCTION public.f4_d1_check_completion()""",
    """
    CREATE FUNCTION public.f4_d1_lock_attempt() RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
    AS $$
    BEGIN
        LOCK TABLE public.f4_d1_attempt IN SHARE ROW EXCLUSIVE MODE;
    END;
    $$
    """,
    "REVOKE ALL ON FUNCTION public.f4_d1_lock_attempt() FROM PUBLIC",
    "REVOKE ALL ON FUNCTION public.f4_d1_check_child() FROM PUBLIC",
    "REVOKE ALL ON FUNCTION public.f4_d1_check_completion() FROM PUBLIC",
)


def upgrade() -> None:
    # Omit implicit PUBLIC access even in roles/configs added by a later operator.
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)
    for statement in SEAL:
        op.execute(statement)
    # F1 revokes PUBLIC usage on "public". Domain usage defaults to PUBLIC, so narrow it too.
    op.execute("REVOKE ALL ON DOMAIN public.f4_d1_sha FROM PUBLIC")


def downgrade() -> None:
    raise RuntimeError("D1 does not downgrade retained storage")
