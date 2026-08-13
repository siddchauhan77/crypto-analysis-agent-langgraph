from crypto_agent.cli import build_parser


def test_chat_parser_accepts_optional_thread() -> None:
    args = build_parser().parse_args(["chat", "--thread", "btc-research"])

    assert args.command == "chat"
    assert args.thread == "btc-research"


def test_evaluate_parser_requires_explicit_live_flag_for_requests() -> None:
    args = build_parser().parse_args(["evaluate", "--repetitions", "2", "--live"])

    assert args.command == "evaluate"
    assert args.repetitions == 2
    assert args.live is True
