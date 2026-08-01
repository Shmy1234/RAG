from ingest.run import parse_args


def test_parse_args_defaults_to_dry_run_without_upload():
    args = parse_args([])

    assert args.dry_run is True
    assert args.upload is False
    assert args.max_chunk_tokens == 1200


def test_parse_args_upload_disables_dry_run_when_explicit():
    args = parse_args(["--upload", "--limit-documents", "1", "--limit-chunks", "1"])

    assert args.upload is True
    assert args.dry_run is False
    assert args.limit_documents == 1
    assert args.limit_chunks == 1


def test_parse_args_supports_embedding_budget_and_confirmation():
    args = parse_args(
        ["--upload", "--yes", "--embedding-batch-token-limit", "1000"]
    )

    assert args.yes is True
    assert args.embedding_batch_token_limit == 1000
