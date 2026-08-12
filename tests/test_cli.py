from crypto_agent.cli import build_parser


def test_chat_parser_accepts_optional_thread() -> None:
    args = build_parser().parse_args(["chat", "--thread", "btc-research"])

    assert args.command == "chat"
    assert args.thread == "btc-research"
