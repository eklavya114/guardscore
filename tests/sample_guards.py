"""Sample Python guard functions used by the py adapter tests."""


def block_everything(request):
    return "block"


def allow_everything(request):
    return "allow"


def dict_with_reason(request):
    return {"decision": "ask", "reason": "needs a human to look"}


def returns_bad_type(request):
    return 42


def returns_bad_decision(request):
    return "maybe"


def dict_without_decision(request):
    return {"reason": "no decision here"}


def crashes(request):
    raise ValueError("sample guard crash")


def echoes_text(request):
    # Blocks if the text mentions rm, to prove the function sees the text.
    return "block" if "rm " in request["text"] else "allow"
